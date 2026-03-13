import easyocr

class OCREngine:
    def __init__(self, languages, confidence_threshold, text_threshold):
        self.reader = easyocr.Reader(languages, gpu=True)
        self.confidence_threshold = confidence_threshold
        self.text_threshold = text_threshold

    def run(self, mask):
        results = self.reader.readtext(
            mask,
            detail=1,
            paragraph=False,
            text_threshold=self.text_threshold,
            allowlist='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789# :[]*!?.,-üäöÜÄÖ+#()&%$§"='
        )

        return [
            (bbox, text, conf)
            for (bbox, text, conf) in results
            if conf > self.confidence_threshold
        ]