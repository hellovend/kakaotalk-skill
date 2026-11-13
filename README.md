# kakaotalk-skill

카카오톡 PC 버전을 Claude Code에서 다루는 스킬이다. Windows 전용.

- 열려 있는 대화방 목록 보기
- 대화 읽기, 새 메시지 기다렸다가 읽기
- 메시지, 사진, 파일 보내기

자세한 사용법과 한계는 [skills/kakaotalk/SKILL.md](skills/kakaotalk/SKILL.md)에 있다.

## 설치

Claude Manager의 설정에서 스킬 저장소에 `hellovend/kakaotalk-skill`을 추가하고 스킬 목록에서 설치한다.

직접 설치하려면 `skills/kakaotalk` 폴더를 `%USERPROFILE%\.claude\skills\kakaotalk`에 복사한다. `pywin32`와 `psutil`이 필요하다.
