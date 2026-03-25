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

    def run(self, mask):
        results = self.reader.readtext(
            mask,
            detail=1,
            paragraph=False,
            text_threshold=self.text_threshold,
            allowlist=OCR_ALLOWLIST,
        )

        return [
            (bbox, text, conf)
            for (bbox, text, conf) in results
            if conf > self.confidence_threshold
        ]
