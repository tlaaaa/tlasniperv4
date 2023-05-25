import base64
import json
import nbtlib
import io
import sys
from loguru import logger
logger.remove()
logger.add("out.log", enqueue=True, rotation="1 MB", backtrace=True, diagnose=True)
logger.add(sys.stderr, colorize=True, format="| <g><d>{time:HH:mm:ss}</d></g> | <g><b>{level}</b></g> | {message} |", level="INFO")

def auc(item, isScan):
  #logger.info(item["item_name"])
  #print(item["item_bytes"])
  if isScan:
    pass
  else:
    try:
      x_bytes = base64.b64decode(item["item_bytes"])
      x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
      
      #not necessary, slows down code
      #with open('cache/item.json', "w") as file:
      #  json.dump(x_object, file, ensure_ascii=False, indent=4)
    except Exception as e:
      logger.info("error occured while printing bytes "+item["item_bytes"]+" item "+item["item_name"])
  