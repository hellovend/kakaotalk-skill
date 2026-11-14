"""카카오톡 PC 조작. 목록과 읽기는 백그라운드로 되고 보내기는 화면 조작 방식이다.

  python -E -X utf8 kakao.py rooms                 열려 있는 대화방 목록 (백그라운드)
  python -E -X utf8 kakao.py read <방이름> [줄수]   대화 읽기 (백그라운드. 클립보드를 잠깐 쓰고 되돌린다)
  python -E -X utf8 kakao.py watch <방이름> [초]    새 메시지가 올 때까지 기다렸다가 화면 글자 인식으로 읽기 (백그라운드. 키보드와 클립보드 안 씀)
  python -E -X utf8 kakao.py send <방이름> <메시지> 메시지 보내기 (창이 앞으로 나오고 마우스가 움직인다)
  python -E -X utf8 kakao.py image <방이름> <그림>  사진으로 보내기 (화면 조작)
  python -E -X utf8 kakao.py file <방이름> <파일>   파일로 보내기 (화면 조작)
  python -E -X utf8 kakao.py selftest              창을 건드리지 않는 자체 점검

대화방은 미리 열려 있어야 한다. 방이름은 창 제목과 정확히 같아야 한다.
"""
import contextlib, ctypes, sys, time
from difflib import SequenceMatcher

try:
    import win32api, win32clipboard, win32con, win32gui, win32process
except ImportError:
    sys.exit("pywin32가 없음. python -m pip install pywin32 psutil pillow 로 설치한다.")

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()  # 창 좌표와 캡처를 실제 화소 단위로 맞춘다

# 클립보드에 올린 내용이 윈도우 클립보드 기록(Win+V)과 클라우드 동기화에 남지 않게 하는 표시
NO_HISTORY = ("ExcludeClipboardContentFromMonitorProcessing", "CanIncludeInClipboardHistory", "CanUploadToCloudClipboard")
# 메모리 덩어리가 아니라 GDI 핸들이라서 바이트로 저장할 수 없는 클립보드 형식
GDI_FORMATS = {2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E}


def kakao_pids():
    import psutil
    return {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "kakaotalk.exe"}


def rooms():
    """보이는 대화방 창 {제목: [hwnd...]}. 메인 창과 이름 없는 창은 뺀다."""
    pids, out = kakao_pids(), {}

    def cb(h, _):
        title = win32gui.GetWindowText(h)
        if (win32gui.IsWindowVisible(h) and title and title != "카카오톡"
                and win32gui.GetClassName(h) == "EVA_Window_Dblclk"
                and win32process.GetWindowThreadProcessId(h)[1] in pids
                and child(h, "RICHEDIT50W")):
            out.setdefault(title, []).append(h)

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
    if len(r[name]) > 1:
        sys.exit("이름이 '%s'인 대화방 창이 %d개라서 어느 쪽인지 모름. 하나만 남기고 닫는다." % (name, len(r[name])))
    return r[name][0]


def scale(h):
    """화면 배율. 고정 좌표는 100%(96 DPI)에서 잰 값이라 이걸 곱한다."""
    return user32.GetDpiForWindow(h) / 96


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
    """대화방을 맨 위로 올리고 입력칸 가운데를 클릭한다. 다른 창이 앞에 있으면 아무것도 보내지 않고 끝낸다.
    ponytail: 이 카카오톡 버전은 신호로 보낸 Enter를 무시해서 백그라운드 전송이 안 된다. 되는 방법을 찾으면 바꾼다."""
    h = room(name)
    raise_window(h)
    l, t, r, b = win32gui.GetWindowRect(child(h, "RICHEDIT50W"))
    click((l + r) // 2, (t + b) // 2)  # Alt 키는 창 메뉴를 열어서 쓰지 않는다
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
    if not text.strip():
        sys.exit("빈 메시지는 보내지 않음")
    focus_room(name)
    with clipboard_borrowed():
        clip_put_text(text)
        tap(ord("V"), ctrl=True)
        tap(win32con.VK_RETURN)


def send_image(name, path):
    """사진으로 보내기. 그림을 클립보드에 넣고 입력칸에 붙여넣는다."""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, "BMP")
    h = focus_room(name)
    with clipboard_borrowed():
        clip_put([(win32con.CF_DIB, buf.getvalue()[14:])])  # BMP 파일 머리 14바이트를 뺀 것이 DIB
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
    s = scale(h)
    click(l + int(108 * s), b - int(30 * s))  # 파일 버튼 (+, 이모티콘, 파일 순서의 세 번째)
    time.sleep(1.2)
    f = win32gui.GetForegroundWindow()
    if win32gui.GetClassName(f) != "#32770" or win32gui.GetWindow(f, win32con.GW_OWNER) != h:
        sys.exit("파일 열기 창이 안 떠서 보내지 않음")
    with clipboard_borrowed():
        clip_put_text(path)
        tap(ord("V"), ctrl=True)
        tap(win32con.VK_RETURN)
    confirm_popup(h, "파일")


def post_key(hwnd, key, mod):
    """다른 창에 Ctrl+키를 백그라운드로 보낸다. 상대 스레드의 키 상태를 잠깐 바꿔서 Ctrl이 눌린 것처럼 만든다."""
    tid = win32process.GetWindowThreadProcessId(hwnd)[0]
    me = win32api.GetCurrentThreadId()
    user32.AttachThreadInput(me, tid, True)
    state = (ctypes.c_ubyte * 256)()
    user32.GetKeyboardState(state)
    saved = bytes(state)
    try:
        state[mod] |= 0x80
        user32.SetKeyboardState(state)
        lparam = (win32api.MapVirtualKey(key, 0) << 16) | 1
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, key, lparam)
        time.sleep(0.15)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, key, lparam | 0xC0000000)
        time.sleep(0.15)
    finally:
        user32.SetKeyboardState((ctypes.c_ubyte * 256).from_buffer_copy(saved))  # Ctrl이 눌린 채로 남지 않게
        user32.AttachThreadInput(me, tid, False)


@contextlib.contextmanager
def clipboard():
    """다른 프로그램이 클립보드를 잡고 있으면 잠깐 기다렸다가 연다."""
    for _ in range(40):
        try:
            win32clipboard.OpenClipboard()
            break
        except Exception:
            time.sleep(0.05)
    else:
        sys.exit("클립보드를 다른 프로그램이 쓰고 있어서 못 씀")
    try:
        yield
    finally:
        win32clipboard.CloseClipboard()


def clip_save():
    """클립보드의 글자, 그림, 복사한 파일 목록 등을 [(형식, 바이트)]로 저장한다."""
    out = []
    with clipboard():
        fmt = win32clipboard.EnumClipboardFormats(0)
        while fmt:
            if fmt not in GDI_FORMATS and not 0x200 <= fmt <= 0x3FF:
                try:
                    out.append((fmt, win32clipboard.GetGlobalMemory(win32clipboard.GetClipboardDataHandle(fmt))))
                except Exception:
                    pass  # 읽을 수 없는 형식은 건너뛴다. 같은 내용의 다른 형식으로 되살아난다
            fmt = win32clipboard.EnumClipboardFormats(fmt)
    return out


def clip_put(items):
    """클립보드를 items로 바꾼다. 클립보드 기록과 클라우드 동기화에는 남지 않게 표시한다."""
    with clipboard():
        win32clipboard.EmptyClipboard()
        for fmt, data in items:
            win32clipboard.SetClipboardData(fmt, data)
        for n in NO_HISTORY:
            win32clipboard.SetClipboardData(win32clipboard.RegisterClipboardFormat(n), b"\0\0\0\0")


def clip_put_text(text):
    clip_put([(win32con.CF_UNICODETEXT, (text + "\0").encode("utf-16-le"))])


def clip_text():
    with clipboard():
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return None


@contextlib.contextmanager
def clipboard_borrowed():
    """클립보드를 잠깐 빌려 쓰고 원래 내용(글자, 그림, 파일 목록)을 되돌린다."""
    old = clip_save()
    try:
        yield
    finally:
        clip_put(old)


def clipboard_history_on():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Clipboard") as k:
            return winreg.QueryValueEx(k, "EnableClipboardHistory")[0] == 1
    except OSError:
        return False


def read(name, lines=30):
    h = room(name)
    lst = child(h, "EVA_VH_ListControl_Dblclk")
    if not lst:
        sys.exit("대화 목록을 못 찾음. 카카오톡 화면 구성이 바뀐 것 같다")
    if clipboard_history_on():
        print("주의: 윈도우 클립보드 기록(Win+V)이 켜져 있어서 읽은 대화가 기록에 남을 수 있다. "
              "카카오톡이 직접 복사하는 거라 막을 수 없다. 남기기 싫으면 watch를 쓰거나 클립보드 기록을 끈다.",
              file=sys.stderr)
    marker = "kakao-read-%d" % time.time_ns()
    with clipboard_borrowed():
        clip_put_text(marker)
        post_key(lst, ord("A"), win32con.VK_CONTROL)
        post_key(lst, ord("C"), win32con.VK_CONTROL)
        time.sleep(0.4)
        got = clip_text()
    if not got or got == marker:
        sys.exit("대화를 읽지 못함")
    return tail(got, lines)


def capture(h):
    """PrintWindow로 창을 캡처한다. 다른 창에 가려져 있어도 되고 키보드나 마우스는 건드리지 않는다.
    최소화된 창은 캡처되지 않는다."""
    import win32ui
    from PIL import Image
    if win32gui.IsIconic(h):
        sys.exit("대화방 창이 최소화되어 있어서 화면을 못 읽음")
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


def chat_area(img, s=1.0):
    """제목줄과 입력칸을 뺀 대화 부분. 입력칸에서 타자 치는 건 변화로 치지 않는다.
    s는 화면 배율. 제목줄과 입력칸 높이는 창 크기가 아니라 배율을 따라간다."""
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
        p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, tmp],
                           capture_output=True, timeout=60)
    finally:
        os.remove(tmp)
    if p.returncode:
        err = p.stderr.decode("utf-8", "replace").strip()
        if "no-korean-ocr" in err:
            sys.exit("한국어 글자 인식기가 없음. 설정 > 시간 및 언어 > 언어에서 한국어를 추가한다.")
        sys.exit("글자 인식 실패: " + err[-500:])
    out = p.stdout.decode("utf-8", "replace")
    return [ln.split("\t", 1)[1].strip() for ln in out.splitlines() if "\t" in ln and ln.split("\t", 1)[1].strip()]


def new_lines(before, after, same=0.85):
    """after에서 before에 없던 줄만 순서대로. 같은 줄이 여러 번 있으면 개수로 센다.
    글자 인식이 같은 줄을 매번 조금 다르게 읽으므로 거의 같은 줄(same 이상 비슷함)은 있던 줄로 본다.
    ponytail: 비슷한 정도로만 맞추니 있던 말과 거의 같은 새 말은 놓칠 수 있다. 문제가 되면 줄 위치도 같이 비교한다."""
    left = list(before)
    out = []
    for x in after:
        if x in left:
            left.remove(x)
            continue
        ratios = [SequenceMatcher(None, y, x).ratio() for y in left]
        if ratios and max(ratios) >= same:
            left.pop(ratios.index(max(ratios)))
        else:
            out.append(x)
    return out


def watch(name, timeout=300, interval=2.0):
    """새 메시지가 올 때까지 대화 부분을 캡처해서 비교한다. 바뀌면 글자를 인식해서 새 줄을 돌려준다.
    키보드, 마우스, 클립보드를 쓰지 않아서 사용자가 타자를 쳐도 방해하지 않는다.
    ponytail: 화면 글자 인식이라 글자가 틀릴 수 있고 화면에 보이는 부분만 읽는다. 정확한 원문이 필요하면 read를 쓴다."""
    h = room(name)
    s = scale(h)
    first = chat_area(capture(h), s)
    base = ocr(first)
    last = first.tobytes()
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(interval)
        if not win32gui.IsWindow(h):
            sys.exit("대화방 창이 닫힘")
        now = chat_area(capture(h), s).tobytes()
        if now == last:
            continue
        time.sleep(1)  # 화면이 다 그려질 때까지 기다린다
        got = new_lines(base, ocr(chat_area(capture(h), s)))
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
    assert new_lines(["오늘 저녁 뭐 먹을까요"], ["오늘 저넉 뭐 먹을까요", "치킨"]) == ["치킨"]  # 인식 오타는 새 줄이 아니다
    # 클립보드: 글자를 빌려 쓰고 되돌리는지
    with clipboard_borrowed():
        clip_put_text("kakao-selftest 가나다")
        assert clip_text() == "kakao-selftest 가나다"
        with clipboard_borrowed():
            clip_put_text("안쪽")
        assert clip_text() == "kakao-selftest 가나다"
    print("ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    need = {"rooms": 1, "read": 2, "watch": 2, "send": 3, "image": 3, "file": 3, "selftest": 1}
    if not a or a[0] not in need or len(a) < need[a[0]]:
        sys.exit(__doc__)
    cmd = a[0]
    if cmd == "rooms":
        print("\n".join(t if len(hs) == 1 else "%s (같은 이름 창 %d개)" % (t, len(hs)) for t, hs in rooms().items())
              or "열린 대화방 없음")
    elif cmd == "read":
        print(read(a[1], int(a[2]) if len(a) > 2 else 30))
    elif cmd == "send":
        send(a[1], a[2])
        print("보냄:", a[1])
    elif cmd == "watch":
        got = watch(a[1], int(a[2]) if len(a) > 2 else 300)
        print("\n".join(got) if got else "새 메시지 없음")
    elif cmd == "image":
        send_image(a[1], a[2])
        print("사진 보냄:", a[1])
    elif cmd == "file":
        send_file(a[1], a[2])
        print("파일 보냄:", a[1])
    elif cmd == "selftest":
        selftest()
