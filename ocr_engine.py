import easyocr

class OCREngine:
    def __init__(self, languages, confidence_threshold):
        self.reader = easyocr.Reader(languages, gpu=True)
        self.confidence_threshold = confidence_threshold

    def run(self, mask):
        results = self.reader.readtext(
            mask,
            detail=1,
            paragraph=False,
            text_threshold=0.4,
            allowlist='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789# :[]*!?.,-üäöÜÄÖ+#()&%$§"='
        )

        return [
            (bbox, text, conf)
            for (bbox, text, conf) in results
            if conf > self.confidence_threshold
        ]