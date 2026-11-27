#import <AVFoundation/AVFoundation.h>

/// Shows an H.264 stream. Both methods may be called from any thread; frames
/// are fed from the stream client's video queue so the interface never
/// holds the picture back.
@interface IPSH264Renderer : AVSampleBufferDisplayLayer
- (void)resetStream;
- (BOOL)enqueueAccessUnit:(NSData *)unit;
/// Nothing can be shown until the next keyframe arrives.
- (BOOL)waitingForKeyframe;
@end
