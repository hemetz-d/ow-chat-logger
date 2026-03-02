import pyautogui
import time

print("Mouse tracker running. Hover over chat corners. Ctrl+C to stop.")

while True:
    x, y = pyautogui.position()
    print(f"Current: x={x}, y={y}")
    time.sleep(1)