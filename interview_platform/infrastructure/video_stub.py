"""Text capture adapter standing in for the future resumable video provider."""

from interview_platform.application.ports import CapturedAnswer


class TextCaptureStub:
    """Make the missing video capability explicit in data and UI."""

    kind = "text_stub"
    message = "Видео в POC не записывается: ответ сохраняется как текстовая имитация."

    def capture(self, content: str) -> CapturedAnswer:
        return CapturedAnswer(
            capture_kind=self.kind,
            content=content,
            media_reference=None,
        )
