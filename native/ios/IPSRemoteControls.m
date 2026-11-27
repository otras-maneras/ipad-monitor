#import "IPSRemoteControls.h"
#import <math.h>

/// Pointer commands go out at most this often.
static const CFTimeInterval kMoveInterval = 1.0 / 45.0;
/// Finger travel, in points, for one wheel step.
static const CGFloat kScrollStep = 24.0;

@interface IPSRemoteTextField : UITextField
@property (nonatomic, copy) void (^backspace)(void);
@end

@implementation IPSRemoteTextField
@synthesize backspace = _backspace;
- (void)deleteBackward {
    if (_backspace) _backspace();
}
- (void)dealloc {
    [_backspace release];
    [super dealloc];
}
@end

@implementation IPSRemoteControls {
    UIView *_pad;               // touchpad surface
    UIView *_direct;            // direct-touch surface, see-through
    IPSRemoteTextField *_field;
    UIButton *_closeButton;
    UIBarButtonItem *_ctrlItem;
    UIBarButtonItem *_altItem;
    BOOL _ctrl;                 // sticky modifiers for the next key
    BOOL _alt;
    BOOL _dragging;             // the left button is held down on the PC
    CGPoint _lastDrag;
    CGFloat _scroll;
    CGFloat _moveX;
    CGFloat _moveY;
    CFTimeInterval _lastMove;
}
@synthesize send = _send;
@synthesize pictureFrame = _pictureFrame;

- (UIButton *)button:(NSString *)title action:(SEL)action {
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
    [button setTitle:title forState:UIControlStateNormal];
    [button setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    button.backgroundColor = [UIColor colorWithWhite:0.15 alpha:0.94];
    [button addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];
    return button;
}

- (UIColor *)padColor {
    return [UIColor colorWithWhite:0 alpha:0.22];
}

- (void)addPanTo:(UIView *)view touches:(NSUInteger)touches action:(SEL)action {
    UIPanGestureRecognizer *pan = [[[UIPanGestureRecognizer alloc] initWithTarget:self action:action] autorelease];
    pan.minimumNumberOfTouches = touches;
    pan.maximumNumberOfTouches = touches;
    [view addGestureRecognizer:pan];
}

- (void)addTapTo:(UIView *)view touches:(NSUInteger)touches action:(SEL)action {
    UITapGestureRecognizer *tap = [[[UITapGestureRecognizer alloc] initWithTarget:self action:action] autorelease];
    tap.numberOfTouchesRequired = touches;
    [view addGestureRecognizer:tap];
}

- (void)addHoldTo:(UIView *)view duration:(CFTimeInterval)duration action:(SEL)action {
    UILongPressGestureRecognizer *hold = [[[UILongPressGestureRecognizer alloc] initWithTarget:self action:action] autorelease];
    hold.minimumPressDuration = duration;
    [view addGestureRecognizer:hold];
}

- (id)initWithFrame:(CGRect)frame {
    if (!(self = [super initWithFrame:frame])) return nil;
    self.hidden = YES;
    self.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;

    _pad = [[UIView alloc] initWithFrame:self.bounds];
    _pad.backgroundColor = [self padColor];
    _pad.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [self addSubview:_pad];
    [_pad release];
    [self addPanTo:_pad touches:1 action:@selector(pan:)];
    [self addPanTo:_pad touches:2 action:@selector(scroll:)];
    [self addTapTo:_pad touches:1 action:@selector(tap:)];
    [self addTapTo:_pad touches:2 action:@selector(rightClick)];
    // Hold still, then move: drag with the left button down.
    [self addHoldTo:_pad duration:0.35 action:@selector(hold:)];
    UIButton *right = [self button:@"Clic derecho" action:@selector(rightClick)];
    right.frame = CGRectMake(18, frame.size.height - 62, 130, 44);
    right.autoresizingMask = UIViewAutoresizingFlexibleTopMargin;
    [_pad addSubview:right];

    _direct = [[UIView alloc] initWithFrame:self.bounds];
    _direct.backgroundColor = [UIColor clearColor];
    _direct.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    _direct.hidden = YES;
    [self addSubview:_direct];
    [_direct release];
    [self addPanTo:_direct touches:1 action:@selector(directPan:)];
    [self addPanTo:_direct touches:2 action:@selector(scroll:)];
    [self addTapTo:_direct touches:1 action:@selector(directTap:)];
    [self addHoldTo:_direct duration:0.5 action:@selector(directHold:)];

    _closeButton = [self button:@"Cerrar" action:@selector(close)];
    _closeButton.frame = CGRectMake(18, 18, 98, 44);
    [self addSubview:_closeButton];

    _field = [[IPSRemoteTextField alloc] initWithFrame:CGRectMake(135, 18, 240, 44)];
    _field.placeholder = @"Escribir en Windows";
    _field.borderStyle = UITextBorderStyleRoundedRect;
    _field.backgroundColor = [UIColor whiteColor];
    _field.autocorrectionType = UITextAutocorrectionTypeNo;
    _field.autocapitalizationType = UITextAutocapitalizationTypeNone;
    _field.delegate = self;
    __block IPSRemoteControls *owner = self;
    _field.backspace = ^{ [owner sendKey:@"backspace"]; };
    UIToolbar *shortcuts = [[[UIToolbar alloc] initWithFrame:CGRectMake(0, 0, frame.size.width, 44)] autorelease];
    NSArray *titles = [self shortcutTitles];
    NSArray *names = [self shortcutNames];
    NSMutableArray *items = [NSMutableArray array];
    for (NSUInteger index = 0; index < titles.count; index++) {
        UIBarButtonItem *item = [[[UIBarButtonItem alloc] initWithTitle:[titles objectAtIndex:index]
                                                                style:UIBarButtonItemStylePlain
                                                               target:self action:@selector(shortcut:)] autorelease];
        item.tag = (NSInteger)index;
        NSString *name = [names objectAtIndex:index];
        if ([name isEqualToString:@"ctrl"]) _ctrlItem = [item retain];
        if ([name isEqualToString:@"alt"]) _altItem = [item retain];
        [items addObject:item];
    }
    shortcuts.items = items;
    _field.inputAccessoryView = shortcuts;
    [self addSubview:_field];
    [_field release];
    return self;
}

- (void)dealloc {
    [_send release];
    [_ctrlItem release];
    [_altItem release];
    [super dealloc];
}

- (void)sendCommand:(NSString *)command {
    if (_send) _send(command);
}

#pragma mark - Keyboard

- (NSArray *)shortcutTitles {
    return @[@"Esc", @"Tab", @"Ctrl", @"Alt", @"Win", @"Supr", @"←", @"↑", @"↓", @"→",
             @"Copiar", @"Pegar", @"Deshacer", @"Alt+Tab"];
}

/// What each shortcut sends: a key name, a sticky modifier, or a combination.
- (NSArray *)shortcutNames {
    return @[@"escape", @"tab", @"ctrl", @"alt", @"win", @"delete", @"left", @"up", @"down", @"right",
             @"ctrl+c", @"ctrl+v", @"ctrl+z", @"alt+tab"];
}

- (void)showModifiers {
    UIColor *active = [UIColor colorWithRed:1.0 green:0.58 blue:0.0 alpha:1.0];
    _ctrlItem.style = _ctrl ? UIBarButtonItemStyleDone : UIBarButtonItemStylePlain;
    _ctrlItem.tintColor = _ctrl ? active : nil;
    _altItem.style = _alt ? UIBarButtonItemStyleDone : UIBarButtonItemStylePlain;
    _altItem.tintColor = _alt ? active : nil;
}

/// Sends one key, together with Ctrl or Alt if they were armed.
- (void)sendKey:(NSString *)name {
    if (_ctrl || _alt) {
        [self sendCommand:[NSString stringWithFormat:@"combo=%@%@%@",
                           _ctrl ? @"ctrl+" : @"", _alt ? @"alt+" : @"", name]];
        _ctrl = NO;
        _alt = NO;
        [self showModifiers];
    } else {
        [self sendCommand:[@"key=" stringByAppendingString:name]];
    }
}

- (void)shortcut:(UIBarButtonItem *)item {
    NSArray *names = [self shortcutNames];
    if (item.tag < 0 || (NSUInteger)item.tag >= names.count) return;
    NSString *name = [names objectAtIndex:(NSUInteger)item.tag];
    if ([name isEqualToString:@"ctrl"]) {
        _ctrl = !_ctrl;
        [self showModifiers];
    } else if ([name isEqualToString:@"alt"]) {
        _alt = !_alt;
        [self showModifiers];
    } else if ([name rangeOfString:@"+"].location != NSNotFound) {
        [self sendCommand:[@"combo=" stringByAppendingString:name]];
    } else {
        [self sendKey:name];
    }
}

- (BOOL)textField:(UITextField *)field shouldChangeCharactersInRange:(NSRange)range replacementString:(NSString *)text {
    // With Ctrl or Alt armed, a letter or digit becomes a shortcut.
    if ((_ctrl || _alt) && text.length == 1) {
        unichar c = [text characterAtIndex:0];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) {
            [self sendKey:[text lowercaseString]];
            return NO;
        }
    }
    // Split long pastes on composed characters so every UTF-8 packet is valid.
    NSMutableData *chunk = [NSMutableData data];
    [text enumerateSubstringsInRange:NSMakeRange(0, text.length)
                             options:NSStringEnumerationByComposedCharacterSequences
                          usingBlock:^(NSString *part, NSRange one, NSRange enclosing, BOOL *stop) {
        if ([part rangeOfCharacterFromSet:[NSCharacterSet newlineCharacterSet]].location != NSNotFound ||
            [part isEqualToString:@"\t"]) {
            if (chunk.length) {
                [self sendCommand:[@"text=" stringByAppendingString:[chunk base64EncodedStringWithOptions:0]]];
                [chunk setLength:0];
            }
            [self sendCommand:[part isEqualToString:@"\t"] ? @"key=tab" : @"key=enter"];
            return;
        }
        NSData *bytes = [part dataUsingEncoding:NSUTF8StringEncoding];
        if (bytes.length > 600) return;
        if (chunk.length + bytes.length > 600) {
            [self sendCommand:[@"text=" stringByAppendingString:[chunk base64EncodedStringWithOptions:0]]];
            [chunk setLength:0];
        }
        [chunk appendData:bytes];
    }];
    if (chunk.length) [self sendCommand:[@"text=" stringByAppendingString:[chunk base64EncodedStringWithOptions:0]]];
    return NO;
}

- (BOOL)textFieldShouldReturn:(UITextField *)field {
    [self sendKey:@"enter"];
    return NO;
}

#pragma mark - Opening and closing

- (void)showSurface:(UIView *)surface {
    [self endDrag];
    [_field resignFirstResponder];
    _field.hidden = YES;
    _pad.hidden = (surface != _pad);
    _direct.hidden = (surface != _direct);
    // Over the live picture the button shouldn't hide much of the desktop.
    _closeButton.alpha = (surface == _direct) ? 0.55 : 1.0;
    self.hidden = NO;
}

- (void)openTouchpad {
    [self showSurface:_pad];
}

- (void)openDirectTouch {
    [self showSurface:_direct];
}

- (void)openKeyboard {
    [self showSurface:nil];
    _field.hidden = NO;
    [_field becomeFirstResponder];
}

- (void)close {
    [self endDrag];
    [_field resignFirstResponder];
    self.hidden = YES;
}

#pragma mark - Pointer

/// Accumulates motion and sends it at a steady rate. Slow strokes move the
/// pointer one to one for aiming; fast ones are multiplied to cross the
/// screen. `flush` sends whatever is left, at the end of a stroke.
- (void)moveByX:(CGFloat)dx y:(CGFloat)dy speed:(CGFloat)speed flush:(BOOL)flush {
    CGFloat gain = 0.8 + speed / 680.0;
    if (gain < 1.0) gain = 1.0;
    if (gain > 3.0) gain = 3.0;
    _moveX += dx * gain;
    _moveY += dy * gain;

    CFTimeInterval now = CFAbsoluteTimeGetCurrent();
    if (!flush && now - _lastMove < kMoveInterval) return;
    _lastMove = now;

    NSInteger x = (NSInteger)_moveX;
    NSInteger y = (NSInteger)_moveY;
    if (x > 150) x = 150;
    if (x < -150) x = -150;
    if (y > 150) y = 150;
    if (y < -150) y = -150;
    _moveX -= x;
    _moveY -= y;
    if (x || y) [self sendCommand:[NSString stringWithFormat:@"move=%ld,%ld", (long)x, (long)y]];
}

- (void)endDrag {
    if (!_dragging) return;
    _dragging = NO;
    _pad.backgroundColor = [self padColor];
    [self sendCommand:@"button=up"];
}

- (void)tap:(UITapGestureRecognizer *)tap {
    [self sendCommand:@"click=left"];
}

- (void)rightClick {
    [self sendCommand:@"click=right"];
}

- (void)pan:(UIPanGestureRecognizer *)pan {
    UIGestureRecognizerState state = pan.state;
    if (state == UIGestureRecognizerStateBegan) {
        _moveX = 0;
        _moveY = 0;
    }
    BOOL ending = (state == UIGestureRecognizerStateEnded);
    if (state != UIGestureRecognizerStateBegan && state != UIGestureRecognizerStateChanged && !ending) return;
    CGPoint delta = [pan translationInView:pan.view];
    [pan setTranslation:CGPointZero inView:pan.view];
    CGPoint velocity = [pan velocityInView:pan.view];
    CGFloat speed = (CGFloat)sqrt((double)(velocity.x * velocity.x + velocity.y * velocity.y));
    [self moveByX:delta.x y:delta.y speed:speed flush:ending];
}

- (void)scroll:(UIPanGestureRecognizer *)pan {
    UIGestureRecognizerState state = pan.state;
    if (state == UIGestureRecognizerStateBegan) _scroll = 0;
    if (state != UIGestureRecognizerStateBegan && state != UIGestureRecognizerStateChanged &&
        state != UIGestureRecognizerStateEnded) return;
    CGPoint delta = [pan translationInView:pan.view];
    [pan setTranslation:CGPointZero inView:pan.view];
    _scroll += delta.y;
    NSInteger steps = (NSInteger)(_scroll / kScrollStep);
    if (!steps) return;
    _scroll -= steps * kScrollStep;
    if (steps > 12) steps = 12;
    if (steps < -12) steps = -12;
    [self sendCommand:[NSString stringWithFormat:@"scroll=%ld", (long)steps]];
}

/// Touchpad drag: the finger rested, so the left button goes down and stays
/// down until the finger lifts.
- (void)hold:(UILongPressGestureRecognizer *)hold {
    UIGestureRecognizerState state = hold.state;
    CGPoint point = [hold locationInView:_pad];
    if (state == UIGestureRecognizerStateBegan) {
        _dragging = YES;
        _lastDrag = point;
        _moveX = 0;
        _moveY = 0;
        _pad.backgroundColor = [UIColor colorWithRed:0.04 green:0.52 blue:1.0 alpha:0.25];
        [self sendCommand:@"button=down"];
    } else if (state == UIGestureRecognizerStateChanged) {
        if (!_dragging) return;
        [self moveByX:point.x - _lastDrag.x y:point.y - _lastDrag.y speed:0 flush:NO];
        _lastDrag = point;
    } else if (state == UIGestureRecognizerStateEnded || state == UIGestureRecognizerStateCancelled ||
               state == UIGestureRecognizerStateFailed) {
        if (!_dragging) return;
        [self moveByX:0 y:0 speed:0 flush:YES];
        [self endDrag];
    }
}

#pragma mark - Direct touch

/// "at=x,y" for a point of this view, as 0-10000 across the picture.
- (NSString *)pointCommand:(CGPoint)point {
    CGRect picture = _pictureFrame;
    if (picture.size.width < 1 || picture.size.height < 1) picture = self.bounds;
    CGFloat x = (point.x - picture.origin.x) / picture.size.width;
    CGFloat y = (point.y - picture.origin.y) / picture.size.height;
    if (x < 0) x = 0;
    if (x > 1) x = 1;
    if (y < 0) y = 0;
    if (y > 1) y = 1;
    return [NSString stringWithFormat:@"at=%ld,%ld", (long)(x * 10000), (long)(y * 10000)];
}

- (void)directTap:(UITapGestureRecognizer *)tap {
    [self sendCommand:[self pointCommand:[tap locationInView:self]]];
    [self sendCommand:@"click=left"];
}

- (void)directHold:(UILongPressGestureRecognizer *)hold {
    if (hold.state != UIGestureRecognizerStateBegan) return;
    [self sendCommand:[self pointCommand:[hold locationInView:self]]];
    [self sendCommand:@"click=right"];
}

/// One finger drags from where it first touched, like on a touch screen.
- (void)directPan:(UIPanGestureRecognizer *)pan {
    UIGestureRecognizerState state = pan.state;
    CGPoint point = [pan locationInView:self];
    if (state == UIGestureRecognizerStateBegan) {
        // The recognizer starts after the finger has already moved a little;
        // press where it actually landed.
        CGPoint travelled = [pan translationInView:self];
        CGPoint start = CGPointMake(point.x - travelled.x, point.y - travelled.y);
        [self sendCommand:[self pointCommand:start]];
        _dragging = YES;
        _lastMove = 0;
        [self sendCommand:@"button=down"];
    } else if (state == UIGestureRecognizerStateChanged) {
        if (!_dragging) return;
        CFTimeInterval now = CFAbsoluteTimeGetCurrent();
        if (now - _lastMove < kMoveInterval) return;
        _lastMove = now;
        [self sendCommand:[self pointCommand:point]];
    } else if (state == UIGestureRecognizerStateEnded || state == UIGestureRecognizerStateCancelled ||
               state == UIGestureRecognizerStateFailed) {
        if (!_dragging) return;
        [self sendCommand:[self pointCommand:point]];
        [self endDrag];
    }
}
@end
