from PIL import ImageGrab
import sys

path = sys.argv[1]
im = ImageGrab.grabclipboard()
im.save(path,'PNG')