#import <UIKit/UIKit.h>

/// Full-screen overlay that turns touches into commands for the PC.
///
/// Touchpad: one finger moves the pointer (faster strokes travel further),
/// a tap clicks, a two-finger tap right-clicks, two fingers scroll, and
/// holding a finger still before moving drags.
/// Direct touch: the picture behaves like a touch screen. A tap clicks where
/// it lands, a long press right-clicks, one finger drags, two fingers scroll.
/// Keyboard: text goes to the focused window, with a row of shortcuts.
@interface IPSRemoteControls : UIView <UITextFieldDelegate>
@property (nonatomic, copy) void (^send)(NSString *command);
/// Where the picture sits inside this view. Direct touch maps onto it.
@property (nonatomic, assign) CGRect pictureFrame;
- (void)openTouchpad;
- (void)openDirectTouch;
- (void)openKeyboard;
- (void)close;
@end
