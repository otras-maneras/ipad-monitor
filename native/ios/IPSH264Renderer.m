#import "IPSH264Renderer.h"
#import <CoreMedia/CoreMedia.h>
#import <QuartzCore/QuartzCore.h>
#import <arpa/inet.h>
#import <string.h>

@implementation IPSH264Renderer {
    CMVideoFormatDescriptionRef _format;
    BOOL _waitingForIDR;
}

- (void)dealloc {
    if (_format) CFRelease(_format);
    [super dealloc];
}

- (void)resetStream {
    @synchronized (self) {
        // Keep the last picture visible while waiting for a new keyframe.
        [self flush];
        if (_format) CFRelease(_format);
        _format = NULL;
        _waitingForIDR = YES;
    }
}

- (BOOL)waitingForKeyframe {
    @synchronized (self) {
        return _waitingForIDR || !_format;
    }
}

- (BOOL)enqueueAccessUnit:(NSData *)unit {
    @synchronized (self) {
        return [self enqueueLocked:unit];
    }
}

- (BOOL)enqueueLocked:(NSData *)unit {
    const uint8_t *bytes = [unit bytes];
    const uint8_t *sets[2] = {NULL, NULL};
    size_t sizes[2] = {0, 0};
    size_t length = [unit length];
    size_t offset = 0;
    BOOL idr = NO;
    while (length - offset >= 4) {
        uint32_t networkSize;
        memcpy(&networkSize, bytes + offset, 4);
        size_t size = ntohl(networkSize);
        offset += 4;
        if (size == 0 || size > length - offset) {
            [self resetStream];
            return NO;
        }
        uint8_t type = bytes[offset] & 31;
        if (type == 5) idr = YES;
        if (type == 7 || type == 8) {
            sets[type - 7] = bytes + offset;
            sizes[type - 7] = size;
        }
        offset += size;
    }
    if (offset != length || !length) {
        [self resetStream];
        return NO;
    }
    if (self.status == AVQueuedSampleBufferRenderingStatusFailed ||
        ![self isReadyForMoreMediaData]) {
        [self resetStream];
    }
    if (![self isReadyForMoreMediaData]) return NO;
    if (!_format || _waitingForIDR) {
        if (!idr || !sets[0] || !sets[1]) return NO;
        OSStatus status = CMVideoFormatDescriptionCreateFromH264ParameterSets(
            kCFAllocatorDefault, 2, sets, sizes, 4, &_format);
        if (status != noErr) {
            [self resetStream];
            return NO;
        }
    }

    CMBlockBufferRef block = NULL;
    CMSampleBufferRef sample = NULL;
    OSStatus status = CMBlockBufferCreateWithMemoryBlock(
        kCFAllocatorDefault, NULL, length, kCFAllocatorDefault, NULL, 0, length,
        kCMBlockBufferAssureMemoryNowFlag, &block);
    if (status == noErr) status = CMBlockBufferReplaceDataBytes(bytes, block, 0, length);
    if (status == noErr) {
        CMSampleTimingInfo timing = {
            kCMTimeInvalid,
            CMTimeMakeWithSeconds(CACurrentMediaTime(), 60000),
            kCMTimeInvalid
        };
        status = CMSampleBufferCreateReady(kCFAllocatorDefault, block, _format, 1,
                                           1, &timing, 1, &length, &sample);
    }
    if (status == noErr) {
        CFArrayRef attachments = CMSampleBufferGetSampleAttachmentsArray(sample, true);
        CFMutableDictionaryRef info = (CFMutableDictionaryRef)CFArrayGetValueAtIndex(attachments, 0);
        CFDictionarySetValue(info, kCMSampleAttachmentKey_DisplayImmediately, kCFBooleanTrue);
        if (!idr) CFDictionarySetValue(info, kCMSampleAttachmentKey_NotSync, kCFBooleanTrue);
        [self enqueueSampleBuffer:sample];
        _waitingForIDR = NO;
    } else {
        [self resetStream];
    }
    if (sample) CFRelease(sample);
    if (block) CFRelease(block);
    return status == noErr;
}
@end
