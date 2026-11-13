"""카카오톡 PC 조작. 목록과 읽기는 백그라운드로 되고 보내기는 화면 조작 방식이다.

  python -I -X utf8 kakao.py rooms                 열려 있는 대화방 목록 (백그라운드)
  python -I -X utf8 kakao.py read <방이름> [줄수]   대화 읽기 (백그라운드. 클립보드를 잠깐 쓰고 글자만 되돌린다)
  python -I -X utf8 kakao.py watch <방이름> [초]    새 메시지가 올 때까지 기다렸다가 화면 글자 인식으로 읽기 (백그라운드. 키보드와 클립보드 안 씀)
  python -I -X utf8 kakao.py send <방이름> <메시지> 메시지 보내기 (창이 앞으로 나오고 마우스가 움직인다)
  python -I -X utf8 kakao.py image <방이름> <그림>  사진으로 보내기 (화면 조작. 클립보드 내용이 사라진다)
  python -I -X utf8 kakao.py file <방이름> <파일>   파일로 보내기 (화면 조작)
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


def raise_window(h):
    """다른 창에 가려져 있으면 클릭이 엉뚱한 창으로 가니까 먼저 맨 위로 올린다."""
    if win32gui.IsIconic(h):
        win32gui.ShowWindow(h, win32con.SW_RESTORE)
    f = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
    win32gui.SetWindowPos(h, win32con.HWND_TOPMOST, 0, 0, 0, 0, f)
    win32gui.SetWindowPos(h, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, f)
    time.sleep(0.4)


def click(x, y):
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.8)


def focus_room(name):
    """대화방을 맨 위로 올리고 입력칸을 클릭한다. 다른 창이 앞에 있으면 아무것도 보내지 않고 끝낸다.
    ponytail: 이 카카오톡 버전은 신호로 보낸 Enter를 무시해서 백그라운드 전송이 안 된다. 되는 방법을 찾으면 바꾼다."""
    h = room(name)
    user32.SetProcessDPIAware()
    raise_window(h)
    l, t, r, b = win32gui.GetWindowRect(h)
    click((l + r) // 2, b - 110)  # Alt 키는 창 메뉴를 열어서 쓰지 않는다
    if win32gui.GetForegroundWindow() != h or win32gui.GetWindowText(h) != name:
        sys.exit("대화방을 앞으로 못 가져와서 보내지 않음")
    return h


def confirm_popup(h, what):
    """사진이나 파일을 고르면 뜨는 카카오톡 전송 확인 창에서 Enter를 누른다."""
    time.sleep(1.5)
    f = win32gui.GetForegroundWindow()
    if f == h or win32process.GetWindowThreadProcessId(f)[1] not in kakao_pids():
        sys.exit("%s 전송 창이 안 떠서 보내지 않음" % what)
    tap(win32con.VK_RETURN)
    time.sleep(2)


def send(name, text):
    """글자 보내기. 창이 앞으로 나오고 마우스가 움직인다."""
    focus_room(name)
    old = clip_get()
    clip_set(text)
    tap(ord("V"), ctrl=True)
    tap(win32con.VK_RETURN)
    clip_set(old)


def send_image(name, path):
    """사진으로 보내기. 그림을 클립보드에 넣고 입력칸에 붙여넣는다. 클립보드 내용은 사라진다."""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, "BMP")
    h = focus_room(name)
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, buf.getvalue()[14:])  # BMP 파일 머리 14바이트를 뺀 것이 DIB
    finally:
        win32clipboard.CloseClipboard()
    tap(ord("V"), ctrl=True)
    confirm_popup(h, "사진")


def send_file(name, path):
    """파일로 보내기. 대화방 아래의 파일 버튼을 누르고 열기 창에 경로를 넣는다.
    복사한 파일을 Ctrl+V로 붙여넣는 방법은 이 카카오톡 버전에서 안 먹힌다."""
    import os
    path = os.path.abspath(path)
    open(path, "rb").close()
    h = focus_room(name)
    l, t, r, b = win32gui.GetWindowRect(h)
    click(l + 108, b - 30)  # 파일 버튼 (+, 이모티콘, 파일 순서의 세 번째)
    time.sleep(1.2)
    f = win32gui.GetForegroundWindow()
    if win32gui.GetClassName(f) != "#32770" or win32gui.GetWindow(f, win32con.GW_OWNER) != h:
        sys.exit("파일 열기 창이 안 떠서 보내지 않음")
    old = clip_get()
    clip_set(path)
    tap(ord("V"), ctrl=True)
    tap(win32con.VK_RETURN)
    clip_set(old)
    confirm_popup(h, "파일")


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


def capture(h):
    """PrintWindow로 창을 캡처한다. 다른 창에 가려져 있어도 되고 키보드나 마우스는 건드리지 않는다.
    최소화된 창은 캡처되지 않는다."""
    import win32ui
    from PIL import Image
    user32.SetProcessDPIAware()
    l, t, r, b = win32gui.GetWindowRect(h)
    w, ht = r - l, b - t
    hdc = win32gui.GetWindowDC(h)
    src = win32ui.CreateDCFromHandle(hdc)
    mem = src.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(src, w, ht)
    mem.SelectObject(bmp)
    try:
        user32.PrintWindow(h, mem.GetSafeHdc(), 2)  # 2 = PW_RENDERFULLCONTENT
        return Image.frombuffer("RGB", (w, ht), bmp.GetBitmapBits(True), "raw", "BGRX", 0, 1)
    finally:
        win32gui.DeleteObject(bmp.GetHandle())
        mem.DeleteDC()
        src.DeleteDC()
        win32gui.ReleaseDC(h, hdc)


def chat_area(img):
    """제목줄과 입력칸을 뺀 대화 부분. 입력칸에서 타자 치는 건 변화로 치지 않는다."""
    s = img.width / 475  # 화면 배율이 달라도 비율로 자른다
    return img.crop((0, int(110 * s), img.width, img.height - int(145 * s)))


def ocr(img):
    """윈도우 기본 글자 인식(한국어)으로 읽은 줄 목록. 글자가 조금씩 틀릴 수 있다."""
    import os, subprocess, tempfile
    from PIL import Image
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.resize((img.width * 2, img.height * 2), Image.LANCZOS).save(tmp)  # 키우면 더 잘 읽힌다
        ps1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr.ps1")
        out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, tmp],
                             capture_output=True, timeout=60).stdout.decode("utf-8", "replace")
    finally:
        os.remove(tmp)
    return [ln.split("\t", 1)[1].strip() for ln in out.splitlines() if "\t" in ln and ln.split("\t", 1)[1].strip()]


def new_lines(before, after):
    """after에서 before에 없던 줄만 순서대로. 같은 줄이 여러 번 있으면 개수로 센다."""
    left = {}
    for x in before:
        left[x] = left.get(x, 0) + 1
    out = []
    for x in after:
        if left.get(x):
            left[x] -= 1
        else:
            out.append(x)
    return out


def watch(name, timeout=300, interval=2.0):
    """새 메시지가 올 때까지 대화 부분을 캡처해서 비교한다. 바뀌면 글자를 인식해서 새 줄을 돌려준다.
    키보드, 마우스, 클립보드를 쓰지 않아서 사용자가 타자를 쳐도 방해하지 않는다.
    ponytail: 화면 글자 인식이라 글자가 틀릴 수 있고 화면에 보이는 부분만 읽는다. 정확한 원문이 필요하면 read를 쓴다."""
    h = room(name)
    first = chat_area(capture(h))
    base = ocr(first)
    last = first.tobytes()
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(interval)
        if not win32gui.IsWindow(h):
            sys.exit("대화방 창이 닫힘")
        now = chat_area(capture(h)).tobytes()
        if now == last:
            continue
        time.sleep(1)  # 화면이 다 그려질 때까지 기다린다
        got = new_lines(base, ocr(chat_area(capture(h))))
        if got:
            return got
        last = now
    return []


def tail(text, lines):
    rows = [r for r in text.replace("\r\n", "\n").split("\n") if r.strip()]
    return "\n".join(rows[-lines:])


def selftest():
    assert tail("a\r\n\r\nb\nc\n", 2) == "b\nc"
    assert tail("a", 5) == "a"
    assert new_lines(["a", "b", "a"], ["b", "a", "a", "c", "a"]) == ["c", "a"]
    assert new_lines([], ["x"]) == ["x"]
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
    elif cmd == "watch":
        got = watch(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 300)
        print("\n".join(got) if got else "새 메시지 없음")
    elif cmd == "image":
        send_image(sys.argv[2], sys.argv[3])
        print("사진 보냄:", sys.argv[2])
    elif cmd == "file":
        send_file(sys.argv[2], sys.argv[3])
        print("파일 보냄:", sys.argv[2])
    elif cmd == "selftest":
        selftest()
    else:
        sys.exit(__doc__)
