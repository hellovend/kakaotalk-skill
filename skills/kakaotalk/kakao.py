"""카카오톡 PC 조작. 목록과 읽기는 백그라운드로 되고 보내기는 화면 조작 방식이다.

  python -I -X utf8 kakao.py rooms                 열려 있는 대화방 목록 (백그라운드)
  python -I -X utf8 kakao.py read <방이름> [줄수]   대화 읽기 (백그라운드. 클립보드를 잠깐 쓰고 글자만 되돌린다)
  python -I -X utf8 kakao.py send <방이름> <메시지> 메시지 보내기 (창이 앞으로 나오고 마우스가 움직인다)
  python -I -X utf8 kakao.py selftest              창을 건드리지 않는 자체 점검

대화방은 미리 열려 있어야 한다. 방이름은 창 제목과 정확히 같아야 한다.
"""
import ctypes, sys, time
import win32api, win32clipboard, win32con, win32gui, win32process

user32 = ctypes.windll.user32


def kakao_pids():
    import psutil
    return {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "kakaotalk.exe"}


def rooms():
    """보이는 대화방 창 {제목: hwnd}. 메인 창과 이름 없는 창은 뺀다."""
    pids, out = kakao_pids(), {}

    def cb(h, _):
        title = win32gui.GetWindowText(h)
        if (win32gui.IsWindowVisible(h) and title and title != "카카오톡"
                and win32gui.GetClassName(h) == "EVA_Window_Dblclk"
                and win32process.GetWindowThreadProcessId(h)[1] in pids
                and child(h, "RICHEDIT50W")):
            out[title] = h

    win32gui.EnumWindows(cb, None)
    return out


def child(h, cls):
    found = []
    win32gui.EnumChildWindows(h, lambda c, _: found.append(c) if win32gui.GetClassName(c) == cls else None, None)
    return found[0] if found else None


def room(name):
    r = rooms()
    if name not in r:
        sys.exit("열려 있는 대화방이 아님: %s / 열린 방: %s" % (name, ", ".join(r) or "없음"))
    return r[name]


def tap(vk, ctrl=False):
    if ctrl:
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(vk, 0, 0, 0)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
    if ctrl:
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.4)


def send(name, text):
    """화면 조작 방식. 창이 앞으로 나오고 마우스가 움직인다.
    ponytail: 이 카카오톡 버전은 신호로 보낸 Enter를 무시해서 백그라운드 전송이 안 된다. 되는 방법을 찾으면 바꾼다."""
    h = room(name)
    user32.SetProcessDPIAware()
    l, t, r, b = win32gui.GetWindowRect(h)
    win32api.SetCursorPos(((l + r) // 2, b - 110))  # 입력칸을 클릭해 창을 앞으로. Alt 키는 메뉴를 열어서 쓰지 않는다
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.8)
    if win32gui.GetForegroundWindow() != h or win32gui.GetWindowText(h) != name:
        sys.exit("대화방을 앞으로 못 가져와서 보내지 않음")
    old = clip_get()
    clip_set(text)
    tap(ord("V"), ctrl=True)
    tap(win32con.VK_RETURN)
    clip_set(old)


def post_key(hwnd, key, mod):
    """다른 창에 Ctrl+키를 백그라운드로 보낸다. 상대 스레드의 키 상태를 잠깐 바꿔서 Ctrl이 눌린 것처럼 만든다."""
    tid = win32process.GetWindowThreadProcessId(hwnd)[0]
    me = win32api.GetCurrentThreadId()
    user32.AttachThreadInput(me, tid, True)
    try:
        state = (ctypes.c_ubyte * 256)()
        user32.GetKeyboardState(state)
        saved = bytes(state)
        state[mod] |= 0x80
        user32.SetKeyboardState(state)
        lparam = (win32api.MapVirtualKey(key, 0) << 16) | 1
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, key, lparam)
        time.sleep(0.15)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, key, lparam | 0xC0000000)
        time.sleep(0.15)
        user32.SetKeyboardState((ctypes.c_ubyte * 256).from_buffer_copy(saved))
    finally:
        user32.AttachThreadInput(me, tid, False)


def clip_get():
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return None
    finally:
        win32clipboard.CloseClipboard()


def clip_set(text):
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        if text is not None:
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def read(name, lines=30):
    h = room(name)
    lst = child(h, "EVA_VH_ListControl_Dblclk")
    old = clip_get()  # 글자만 되돌린다. 복사해 둔 파일이나 그림은 사라진다
    marker = "\0kakao-read\0"
    clip_set(marker)
    post_key(lst, ord("A"), win32con.VK_CONTROL)
    post_key(lst, ord("C"), win32con.VK_CONTROL)
    time.sleep(0.4)
    got = clip_get()
    clip_set(old)
    if got in (None, marker):
        sys.exit("대화를 읽지 못함")
    return tail(got, lines)


def tail(text, lines):
    rows = [r for r in text.replace("\r\n", "\n").split("\n") if r.strip()]
    return "\n".join(rows[-lines:])


def selftest():
    assert tail("a\r\n\r\nb\nc\n", 2) == "b\nc"
    assert tail("a", 5) == "a"
    print("ok")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "rooms":
        print("\n".join(rooms()) or "열린 대화방 없음")
    elif cmd == "read":
        print(read(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 30))
    elif cmd == "send":
        send(sys.argv[2], sys.argv[3])
        print("보냄:", sys.argv[2])
    elif cmd == "selftest":
        selftest()
    else:
        sys.exit(__doc__)
