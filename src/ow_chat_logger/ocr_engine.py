import easyocr

OCR_ALLOWLIST = (
    'abcdefghijklmnopqrstuvwxyz'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '0123456789'
    '# :[]*!?.,-üäöÜÄÖ+#()&%$§"='
)


class OCREngine:
    def __init__(self, languages, confidence_threshold, text_threshold, use_gpu=True):
        self.confidence_threshold = confidence_threshold
        self.text_threshold = text_threshold
        self.reader = self._create_reader(languages, use_gpu)

    @staticmethod
    def _create_reader(languages, use_gpu):
        if not use_gpu:
            return easyocr.Reader(languages, gpu=False)
        try:
            return easyocr.Reader(languages, gpu=True)
        except Exception:
            return easyocr.Reader(languages, gpu=False)

    def run(self, mask, *, confidence_threshold=None, text_threshold=None):
        confidence_threshold = (
            self.confidence_threshold
            if confidence_threshold is None
            else confidence_threshold
        )
        text_threshold = (
            self.text_threshold
            if text_threshold is None
            else text_threshold
        )
        results = self.reader.readtext(
            mask,
            detail=1,
            paragraph=False,
            text_threshold=text_threshold,
            allowlist=OCR_ALLOWLIST,
        )

        return [
            (bbox, text, conf)
            for (bbox, text, conf) in results
            if conf > confidence_threshold
        ]
