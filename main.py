#apologies to anyone trying to understand this code.

#setting up logger, has up to 50 1mb files of logs.
from loguru import logger
import sys
import datetime
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
logger.remove()
logger.add("logs/out.log", enqueue=True, rotation="1 MB", retention=50, backtrace=True, diagnose=True)
logger.add(sys.stderr, colorize=True, format="| <g><d>{time:HH:mm:ss}</d></g> | <g><b>{level}</b></g> | {message} |", level="INFO")

start_time = datetime.datetime.now()

#real code starts here
import json
import requests
import base64
import nbtlib
import io
import re
import pickle
from collections import Counter
import mcfc

#variable init
times = []
lastUpdated = 0
updateTime = 0
nameLookup = {}
LBIN = {}
lastTry = 0
count = 0
recentSellers = []
flips = []
petlbin = {}
armourlbin = {}
skipGem = []
bigcount = 0

#loading saved variables from cache/data
#generally, cache is just lookup dictionaries, which speed up the program, reducing the need for nbt decoding
#data is saved averages/lowestbin data, which is used to calculate prices
with open("cache/nameLookup.json", "r") as f:
  nameLookup = json.load(f)
with open("data/lbin.json", "r") as f:
  avglbin = json.load(f)
with open("data/volume.json", "r") as f:
  volume = json.load(f)
with open("data/sold.json", "r") as f:
  avgsold = json.load(f)
with open("cache/skinLookup.json", "r") as f:
  skinLookup = json.load(f)
with open("cache/GEM.json", "r") as f:
  gemLookup = json.load(f)
with open("cache/heldItemLookup.json", "r") as f:
  heldItemLookup = json.load(f)
with open("data/pets/lbindata.pkl", "rb") as f:
  petlbindata = pickle.load(f)
with open("data/pets/sold.pkl", "rb") as f:
  petavgsold = pickle.load(f)
with open("data/pets/volume.pkl", "rb") as f:
  petvolume = pickle.load(f)
try:
  with open("data/armour/lbindata.pkl", "rb") as f:
    armourlbindata = pickle.load(f)
  with open("data/armour/sold.pkl", "rb") as f:
    armouravgsold = pickle.load(f)
  with open("data/armour/volume.pkl", "rb") as f:
    armourvolume = pickle.load(f)
except Exception as e:
  logger.opt(exception=e).error("error while loading")
  armourlbindata = {}
  armouravgsold = {}
  armourvolume = {}

#functions!! these should be mostly making sense
def milliTime():
  return (int(time.time()*1000))

def formatNumber(number):
  number = round(number/1000, 0)*1000
  if number / 1_000_000_000 > 1 or number / 1_000_000_000 < -1:
    formattedNumber = str(round(number / 1_000_000_000, 2)) + "b"
  elif number / 1_000_000 > 1 or number / 1_000_000 < -1:
    formattedNumber = str(round(number / 1_000_000, 2)) + "m"
  elif number / 1_000 > 1 or number / 1_000 < -1:
    formattedNumber = str(round(number / 1_000, 2)) + "k"
  else:
    formattedNumber = str(round(number, 0))
  return formattedNumber
  
def removeFormatting(string):
  unformattedString = re.sub("§.", "", string)
  return unformattedString

#allows for the writing of date objects in json which can be interpreted in js
def handler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    elif isinstance(obj, ...):
        return ...
    else:
        raise TypeError

#literally just a request, returns json object of a certain auction page
def getApiPage(page):
  try:
    api = requests.get("https://api.hypixel.net/skyblock/auctions?page="+str(page)).json()
    return api
  except Exception as e:
    logger.opt(exception=e).error("error occured while requesting api")

#parses and scans a certain page of the auction house
def fetchPage(pg):
  try: 
    global times
    page = getApiPage(pg)
    checkpoint = datetime.datetime.now()
    smallcount = 0
    
    for item in page["auctions"]:
      smallcount += 1
      auc(item, False)
      timetaken = datetime.datetime.now() - checkpoint
      #print("Parsed an item. Time taken: "+ str(timetaken))
      checkpoint = datetime.datetime.now()
      times.append(timetaken)
    print("Fetched page " + str(pg) + ", finding "+str(smallcount) + " auctions.")
  except Exception as e:
    logger.opt(exception=e).error("error occured while parsing page "+str(pg))
#parses and scans ALL the pages of the auction house.
async def fetchAll(pages):
    with ThreadPoolExecutor(max_workers=5) as executor:
        # allows for 5 threads to be operated at once: reduces the impact of latency. having too many slows it down further
        _ = [executor.submit(fetchPage, pg) for pg in range(pages)]

#auction parsing, slightly differs depending on whether it's just scanning (looking for flips) or not scanning (calculating more price data)
def auc(item, isScan):
  #probably issues with needing this many global variables in this function. what can you do.
  global nameLookup, LBIN, lastUpdated, count, avglbin, flips, skinLookup, heldItemLookup, petlbindata, petlbin, avgsold, petavgsold, petvolume, gemLookup, armourvolume, armouravgsold, armourlbindata, armourlbin, bigcount
  #logger.info(item["item_name"])
  #print(item["item_bytes"])
  bigcount += 1
  
  #ignores non-bin auctions
  if item["bin"]:
    itemName = str(item["item_name"])
    startingBid = int(item["starting_bid"])
    itemLore = str(item["item_lore"])
    petInfo = None
    armourInfo = None
    #insert initial blacklist here. or not.
    try:
      if "[Lvl" in itemName: #checks if item is a pet or not
        itemID = "PET_"+itemName.split("] ")[1].replace(" ✦", "").replace(" ", "_").upper()
        petLevel = int(itemName.split("]")[0].replace("[Lvl ", ""))
        if petLevel == 100:
          petLevelRange = 100
        elif petLevel <= 69:
          petLevelRange = 0
        elif petLevel <= 84:
          petLevelRange = 70
        elif petLevel <= 94:
          petLevelRange = 85
        elif petLevel <= 99:
          petLevelRange = 95
        else:
          petLevelRange = round(petLevel/10)*10
        petCandied = bool("Pet Candy Used" in itemLore)
        petRarity = item["tier"]
        #print(petLevel)
        if ("✦" in itemName): #checks if pet is skinned or not
          firstLine = itemLore.split("\n\n")[0]
          if firstLine+itemID in skinLookup:
            skin = skinLookup[firstLine+itemID]
          else:
            x_bytes = base64.b64decode(item["item_bytes"]) #okay. could theoretically make it more "efficient" if there were checks for if the nbt object was created yet. however no.
            x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
            skin = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"skin\":\"")[1].split("\",")[0]
            skinLookup[firstLine+itemID] = skin
        else:
          skin = None
        if ("Held Item:") in itemLore: #lf held item
          heldLine = itemLore.split("Held Item: ")[1].split("\n")[0]
          if heldLine in heldItemLookup:
            heldItem = heldItemLookup[heldLine]
          else:
            x_bytes = base64.b64decode(item["item_bytes"])
            x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
            heldItem = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"heldItem\":\"")[1].split("\",")[0]
            heldItemLookup[heldLine] = heldItem
          if ("SKILL_BOOST" in heldItem or "SKILLS_BOOST" in heldItem or petLevelRange == 0):
            heldItem = None
        else:
          heldItem = None
        petInfo = (itemID, petRarity, petLevelRange, skin, heldItem, petCandied)

        #print(petInfo)
      else: #hoes can have the same name but different item id. it's really silly. adds extra information to the lookup query if its a hoe to avoid the system getting confused
        isHoe = False
        for notId in ("Euclid's Wheat", "Gauss Carrot", "Newton Nether Warts", "Pythagorean Potato", "Turing Sugar Cane"):
          if notId in itemName:
            isHoe = True
            hoelookup = itemName + item["tier"] + str(len(itemLore.split("Counter: ")[1].split("\n\n")[0])) + str(itemLore.count("§ka§r"))
            if hoelookup in nameLookup:
              itemID = nameLookup[hoelookup]
            else:
              x_bytes = base64.b64decode(item["item_bytes"])
              x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
              itemID = x_object["i"][0]["tag"]["ExtraAttributes"]["id"]
              nameLookup[hoelookup] = itemID
        if itemName in nameLookup and not isHoe:
          itemID = nameLookup[itemName]
        else:
          x_bytes = base64.b64decode(item["item_bytes"])
          x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
          itemID = x_object["i"][0]["tag"]["ExtraAttributes"]["id"]
          nameLookup[itemName] = itemID
          #with open('cache/item.json', "w") as file:
          #  json.dump(x_object, file, ensure_ascii=False, indent=4)
      if item["category"] == "armor": #armour!!
        #stars, ult enchant, gemstone/slots, recomb, other (skin, etc idk, item specific things), reforge?
        otherInfo = ""

        lastLine = itemLore.split("\n")[-1]
        if "§l§ka§r" in lastLine:
          isRecombobulated = True
        else:
          isRecombobulated = False
        
        armourStars = itemName.count("✪")
        if armourStars < 5:
          armourStars = 0
        if "➊" in itemName: armourStars = 6
        elif "➋" in itemName: armourStars = 7
        elif "➌" in itemName: armourStars = 8
        elif "➍" in itemName: armourStars = 9
        elif "➎" in itemName: armourStars = 10

        if "⚚ " in itemName:
          otherInfo = otherInfo + "|frag"

        if " ✦" in itemName:
          firstLine = itemLore.split("\n\n")[0]
          if firstLine+itemID in skinLookup:
            skin = skinLookup[firstLine+itemID]
          else:
            x_bytes = base64.b64decode(item["item_bytes"]) #okay. could theoretically make it more "efficient" if there were checks for if the nbt object was created yet. however no.
            x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
            skin = x_object["i"][0]["tag"]["ExtraAttributes"]["skin"]
            skinLookup[firstLine+itemID] = skin
        elif "✿ " in itemName: #goofed up code i guess- dye = skin = dye = skin but yeah so its always a skin now fuck you
          thelastbitofthelore = itemLore.split("\n\n")[-1].split("\n")[0]
          if "This item can be reforged!" in thelastbitofthelore:
            thelastbitofthelore = itemLore.split("\n\n")[-1].split("\n")[1]
          if thelastbitofthelore in skinLookup:
            skin = skinLookup[thelastbitofthelore]
          else:
            x_bytes = base64.b64decode(item["item_bytes"]) #okay. could theoretically make it more "efficient" if there were checks for if the nbt object was created yet. however no.
            x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
            skin = x_object["i"][0]["tag"]["ExtraAttributes"]["dye_item"]
            skinLookup[thelastbitofthelore] = skin
        else:
          skin = None

        armourReforges = ("Submerged", "Festive", "Jaded", "Loving", "Renowned", "Giant", "Ancient", "Mossy") #necrotic?
        armourReforge = None
        for aReforge in armourReforges:
          if aReforge == itemName.split(" ")[0]:
            armourReforge = aReforge

        checkSlots = ("Necron's", "Storm's", "Goldor's", "Maxor's", "Sorrow", "Divan")
        for slotItem in checkSlots:
          if slotItem in itemName and item["uuid"] not in skipGem:
            if " ✦" not in itemName:
              gemLine = itemLore.split("\n\n")[0].split("\n")[-1]
            else:
              gemLine = itemLore.split("\n\n")[1].split("\n")[-1]
            if gemLine in gemLookup:
              gemSaved = gemLookup[gemLine]
              gems = gemSaved[0]
              slotsUnlocked = gemSaved[1]
            else:
              x_bytes = base64.b64decode(item["item_bytes"])
              x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
              if x_object["i"][0]["tag"]["ExtraAttributes"].get("gems"):
                gemObj = x_object["i"][0]["tag"]["ExtraAttributes"]["gems"]
                gemSaved = []
                gemSaved.append([])
                for slot in gemObj:
                  if slot != "unlocked_slots" and "_gem" not in slot:
                    if "UNIVERSAL" in slot or "DEFENSIVE" in slot or "COMBAT" in slot or "MINING" in slot or "OFFENSIVE" in slot:
                      gemType = gemObj[slot+"_gem"]
                      if "quality" in gemObj[slot]:
                        gemSaved[0].append(gemObj[slot]["quality"] + "_" + gemType)
                      else:
                        gemSaved[0].append(gemObj[slot] + "_" + gemType)
                    else:
                      if "quality" in gemObj[slot]:
                        gemSaved[0].append(gemObj[slot]["quality"] + "_" + list(slot.upper().split("_"))[0])
                      else:
                        gemSaved[0].append(gemObj[slot] + "_" + list(slot.upper().split("_"))[0])
                gemSaved.append([])
                if gemObj.get("unlocked_slots"):
                  for slot in gemObj["unlocked_slots"]:
                    gemSaved[1].append(str(slot))
              else:
                gemSaved = [None, None]
              mcfc.echo(gemLine.replace("§", "&") + "&r " +str(gemSaved))
              if int(x_object["i"][0]["tag"]["ExtraAttributes"]["timestamp"].split(" ")[0].split("/")[-1]) > 21:
                gemLookup[gemLine] = gemSaved
              else:
                #print("OLD ITEM OLD ITEM SLOWING EVERYTHING DOWN")
                skipGem.append(item["uuid"])
        if "gemSaved" in locals():
          unlockedSlots = gemSaved[1]
          if type(unlockedSlots) == list:
            unlockedSlots = tuple(unlockedSlots)
        else:
          unlockedSlots = None
                #this is needed as older items have slots unlocked but do not explicitly say so in the nbt data
        enchants = {
          "Last Stand V": "LS5",
          "Legion V": "L5",
          "Wisdom V": "W5"
        }
        ultimateEnchant = None
        for enchant in enchants:
          if enchant in itemLore:
            ultimateEnchant = enchants[enchant]
        
        """if "Bobbin' Time V" in itemLore:
          x_bytes = base64.b64decode(item["item_bytes"])
          x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
          itemID = x_object["i"][0]["tag"]["ExtraAttributes"]["id"]
          nameLookup[itemName] = itemID
          with open('cache/item.json', "w") as file:
            json.dump(x_object, file, ensure_ascii=False, indent=4)"""

        armourInfo = (itemID, armourStars, skin, armourReforge, unlockedSlots, isRecombobulated, ultimateEnchant, otherInfo)
        #print(armourInfo)
        
      #then attributes seperately ¿
      
    except Exception:
      logger.opt(exception=Exception).error("error occured while parsing item id "+item["item_bytes"]+" item "+item["item_name"])
    
    if isScan: #if trying to calculate flips, no need to save prices (that will be done on a subsequent iteration)
      if item["start"] > lastUpdated - 60_000:
        count = count + 1
        itemValue = 0
        flipFound = False
#need to add gemstones thing, neeed an avg bazaar endpoint to help calc value or something
        try: 
          if petInfo is not None:
            if petInfo in petlbindata and petInfo in petlbin and petInfo in petavgsold and petInfo in petvolume:
              calcindex = str(petInfo)
              calclbin = petlbin[petInfo]
              calcavgsold = petavgsold[petInfo]
              calcavglbin = petlbindata[petInfo]
              calcvolume = petvolume[petInfo]
          elif armourInfo is not None:
            if armourInfo in armourlbindata and armourInfo in armourlbin and armourInfo in armouravgsold and armourInfo in armourvolume:
              calcindex = str(armourInfo)
              calclbin = armourlbin[armourInfo]
              calcavgsold = armouravgsold[armourInfo]
              calcavglbin = armourlbindata[armourInfo]
              calcvolume = armourvolume[armourInfo]
          else:
            if itemID in LBIN and itemID in avgsold and itemID in avglbin and itemID in volume:
              calcindex = itemID
              calclbin = LBIN[itemID]
              calcavgsold = avgsold[itemID]
              calcavglbin = avglbin[itemID]
              calcvolume = volume[itemID]
          if "calcindex" in locals():
            if calcvolume > 0:
              lbinprofit = calclbin - startingBid
              avglbinprofit = calcavglbin - startingBid
              avgsoldprofit = calcavgsold - startingBid
              estimatedTime = 24 / calcvolume
              flipValue = lbinprofit / estimatedTime
              if lbinprofit > 100_000:
                print("~-~-~-~-~-~-~-~-~-~-~-~-~-~-")
                print(calcindex + ": "+ formatNumber(startingBid))
                print("LBIN: "+formatNumber(calclbin) + "(" + formatNumber(lbinprofit) + ")")
                print("AVG_LBIN: "+formatNumber(calcavglbin) + "(" + formatNumber(avglbinprofit) + ")")
                print("AVG_SOLD: "+formatNumber(calcavgsold) + "(" + formatNumber(avgsoldprofit) + ")")
                print("VOLUME: "+str(round(calcvolume, 2)))
                print("EST_TIME: " + str(round(estimatedTime, 2)))
                print("VALUE: "+formatNumber(flipValue) + "("+str(round(flipValue/lbinprofit*100, 2))+"%)")
              if lbinprofit > 0 and avglbinprofit > 0 and avgsoldprofit > 0:
                if lbinprofit + avglbinprofit + avgsoldprofit > 1_000_000:
                  if calcvolume > 10:
                    if lbinprofit / startingBid > 0.06:
                      if calclbin > calcavgsold * 1.2:
                        target = calcavgsold
                      else:
                        target = calclbin * 0.998 - 1000
                      target = int(int(target / 10_000) * 10_000 - 1)
                      flips.append({
                      "itemName": itemName,
                      "id": item["uuid"],
                      "startingBid": startingBid,
                      "target": target,
                      "purchaseAt": json.dumps(datetime.datetime.fromtimestamp(int((item["start"] + 19000) / 1000)), default=handler).replace('"',"") + "Z",
                      "notes": "Index:"+str(calcindex)+"\nVolume:"+str(int(calcvolume*100)/100),
                      "rarity": item["tier"],
                    })
                    
        except Exception as e:
          logger.opt(exception=e).error("Exception raised while calculating flip.")
    
    else:
        #if not scanning, just see if there is a cheaper one on ah, if not set it as lbin.
        if itemID in LBIN:
          if LBIN[itemID] > startingBid:
            LBIN[itemID] = startingBid
        else:
          LBIN[itemID] = startingBid
        
        if petInfo is not None:  
          if petInfo not in petlbin:
            petlbin[petInfo] = startingBid
          else:
            if petlbin[petInfo] > startingBid:
              petlbin[petInfo] = startingBid
        if armourInfo is not None:
          if armourInfo not in armourlbin:
            armourlbin[armourInfo] = startingBid
          else:
            if armourlbin[armourInfo] > startingBid:
              armourlbin[armourInfo] = startingBid
          
        
#scanning and parsing the "recently ended" auctions. items here don't show lore so nbt parsing is needed every time.
def doEnded():
  global volume, avgsold, recentSellers, petavgsold, petvolume, armouravgsold, armourvolume
  try:
    start_of_ended = datetime.datetime.now()
    recentlyEnded = requests.get("https://api.hypixel.net/skyblock/auctions_ended").json()
    with open("cache/recentlyEnded.json", "w") as f:
      f.truncate(0)
      json.dump(recentlyEnded, f, indent=4, ensure_ascii=False)
    for item in recentlyEnded["auctions"]:
      x_bytes = base64.b64decode(item["item_bytes"])
      x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
      itemID = str(x_object["i"][0]["tag"]["ExtraAttributes"]["id"])
      itemName = removeFormatting(x_object["i"][0]["tag"]["display"]["Name"])
      itemLore = "\n".join(x_object["i"][0]["tag"]["display"]["Lore"]) #formats the lore so it's like how its formatted for normal auctions (long string), instead of a list
      if "[Lvl" in itemName:
        itemID = "PET_"+itemName.split("] ")[1].replace(" ✦", "").replace(" ", "_").upper()
        petLevel = int(itemName.split("]")[0].replace("[Lvl ", ""))
        #pet level setting shennanigans. random numbers pulled out of my ass.
        if petLevel == 100: petLevelRange = 100
        elif petLevel <= 69: petLevelRange = 0
        elif petLevel <= 84: petLevelRange = 70
        elif petLevel <= 94: petLevelRange = 85
        elif petLevel <= 99: petLevelRange = 95
        else: petLevelRange = round(petLevel/10)*10
        petCandied = bool("Pet Candy Used" in itemLore)
        petRarity = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"tier\":\"")[1].split("\",")[0]
        if ("✦" in itemName):
          skin = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"skin\":\"")[1].split("\",")[0]
        else: skin = None
        if ("Held Item:") in itemLore:
          heldItem = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"heldItem\":\"")[1].split("\",")[0]
          if ("SKILL_BOOST" in heldItem or "SKILLS_BOOST" in heldItem or petLevelRange == 0):
            heldItem = None
        else: heldItem = None
        #wow the code is much easier when you just parse nbt every time.
        petInfo = (itemID, petRarity, petLevelRange, skin, heldItem, petCandied) #petinfo is a tuple which describes the pet
        if petInfo in petvolume: petvolume[petInfo] = petvolume[petInfo] + 1
        else: petvolume[petInfo] = 0
        if petInfo in petavgsold: petavgsold[petInfo] = int(petavgsold[petInfo] * 0.96 + item["price"] * 0.04)
        else: petavgsold[petInfo] = item["price"]
        #print(petInfo)
      #return to code which is not specific to pets
      lastLine = itemLore.split("\n")[-1]
      isCategoryArmour= False
      armourParts = ["HELMET", "CHESTPLATE", "LEGGINGS", "BOOTS"]
      for part in armourParts:
        if part in lastLine:
          isCategoryArmour = True
      if isCategoryArmour:
        otherInfo = ""
        if "§l§ka§r" in lastLine:
          isRecombobulated = True
        else:
          isRecombobulated = False
        
        armourStars = itemName.count("✪")
        if armourStars < 5:
          armourStars = 0
        if "➊" in itemName: armourStars = 6
        elif "➋" in itemName: armourStars = 7
        elif "➌" in itemName: armourStars = 8
        elif "➍" in itemName: armourStars = 9
        elif "➎" in itemName: armourStars = 10

        if "⚚ " in itemName:
          otherInfo = otherInfo + "|frag"

        if " ✦" in itemName:
            skin = x_object["i"][0]["tag"]["ExtraAttributes"]["skin"]
        elif "✿ " in itemName: #goofed up code i guess- dye = skin = dye = skin but yeah so its always a skin now fuck you
            skin = x_object["i"][0]["tag"]["ExtraAttributes"]["dye_item"]
        else:
          skin = None

        armourReforges = ("Submerged", "Festive", "Jaded", "Loving", "Renowned", "Giant", "Ancient", "Mossy") #necrotic?
        armourReforge = None
        for aReforge in armourReforges:
          if aReforge == itemName.split(" ")[0]:
            armourReforge = aReforge

        checkSlots = ("Necron's", "Storm's", "Goldor's", "Maxor's", "Sorrow", "Divan")
        for slotItem in checkSlots:
          if slotItem in itemName:
              if x_object["i"][0]["tag"]["ExtraAttributes"].get("gems"):
                gemObj = x_object["i"][0]["tag"]["ExtraAttributes"]["gems"]
                gemSaved = []
                gemSaved.append([])
                for slot in gemObj:
                  if slot != "unlocked_slots" and "_gem" not in slot:
                    if "UNIVERSAL" in slot or "DEFENSIVE" in slot or "COMBAT" in slot or "MINING" in slot or "OFFENSIVE" in slot:
                      gemType = gemObj[slot+"_gem"]
                      if "quality" in gemObj[slot]:
                        gemSaved[0].append(gemObj[slot]["quality"] + "_" + gemType)
                      else:
                        gemSaved[0].append(gemObj[slot] + "_" + gemType)
                    else:
                      if "quality" in gemObj[slot]:
                        gemSaved[0].append(gemObj[slot]["quality"] + "_" + list(slot.upper().split("_"))[0])
                      else:
                        gemSaved[0].append(gemObj[slot] + "_" + list(slot.upper().split("_"))[0])
                gemSaved.append([])
                if gemObj.get("unlocked_slots"):
                  for slot in gemObj["unlocked_slots"]:
                    gemSaved[1].append(str(slot))
              else:
                gemSaved = [None, None]
        if "gemSaved" in locals():
          unlockedSlots = gemSaved[1]
          if type(unlockedSlots) == list:
            unlockedSlots = tuple(unlockedSlots)
        else:
          unlockedSlots = None
                #this is needed as older items have slots unlocked but do not explicitly say so in the nbt data
        enchants = {
          "Last Stand V": "LS5",
          "Legion V": "L5",
          "Wisdom V": "W5"
        }
        ultimateEnchant = None
        for enchant in enchants:
          if enchant in itemLore:
            ultimateEnchant = enchants[enchant]
        armourInfo = (itemID, armourStars, skin, armourReforge, unlockedSlots, isRecombobulated, ultimateEnchant, otherInfo)
        if armourInfo in armourvolume: armourvolume[armourInfo] = armourvolume[armourInfo] + 1
        else: armourvolume[armourInfo] = 0
        if armourInfo in armouravgsold: armouravgsold[armourInfo] = int(armouravgsold[armourInfo] * 0.96 + item["price"] * 0.04)
        else: armouravgsold[armourInfo] = item["price"]


      
      #dictionary of the most 1000 recent sellers. may be used for something in the future.
      recentSellers.append(item["seller"])
      if itemID in volume:
        volume[itemID] = volume[itemID] + 1
      else:
        volume[itemID] = 0
      if itemID in avgsold:
        avgsold[itemID] = int(avgsold[itemID] * 0.96 + item["price"] * 0.04)
      else:
        avgsold[itemID] = item["price"]
    if len(recentSellers) > 1000:
      recentSellers = recentSellers[-999:]
    sellerCount = Counter(recentSellers)
    #print(sellerCount.most_common(10))
    
    logger.info("Fetched Ended Auctions, "+str(len(recentlyEnded["auctions"]))+" auctions found. Time Taken: "+str(datetime.datetime.now() - start_of_ended))
  except Exception:
    logger.opt(exception=Exception).error("error occured while fetching ended auctions")

def main():
  global lastUpdated, times, nameLookup, lastTry, LBIN, count, updateTime, volume, flips, skinLookup, heldItemLookup, petlbindata, petlbin, armourlbin, bigcount
  api = getApiPage(0)
  if api != None:
    if api['success'] and ( api["lastUpdated"] != lastUpdated ):
      lastUpdated = api["lastUpdated"]
      logger.info("time after api update: "+str(milliTime() - lastUpdated))
      if updateTime == 0:
        updateTime = lastUpdated
      else:
        updateTime = milliTime()
      ##do flip calculations here
        count = 0
        times = []
        flips = []
        beforescan = datetime.datetime.now()
        for item in api["auctions"]:
          itemStart = datetime.datetime.now()
          auc(item, True)
          times.append(datetime.datetime.now() - itemStart)
        logger.info(str(count)+" new items have been scanned, with a total time taken of "+str(datetime.datetime.now() - beforescan)+".\nFastest time: "+str(times[0])+" | Median time: "+str(times[int(len(times) / 2)]) + " | Slowest time: "+str(times[-1]))
      #print(flips)
      if len(flips) > 0:
        payload = {
          "flips": flips
        }
        with open("flips.json", "w") as file:
          json.dump(payload, file, ensure_ascii=False)
      #caching prices here yeah
      times = []
      bigcount = 0
      LBIN = {}
      petlbin = {}
      armourlbin = {}
      beforeparse = datetime.datetime.now()
      ####REMOVE AFTER WORKING
      with open('cache/api.json', "w") as file:
        json.dump(api, file, ensure_ascii=False, indent=4)  
  
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)
      future = asyncio.ensure_future(fetchAll(api["totalPages"]))
      loop.run_until_complete(future)
      #await fetch_tasks
      times.sort()
      logger.info("Fetching Complete. "+str(len(times))+" items parsed, with a total time taken of "+str(datetime.datetime.now() - beforeparse)+".\nFastest time: "+str(times[0])+" | Median time: "+str(times[int(len(times) / 2)]) + " | Slowest time: "+str(times[-1]))
      logger.info("lastUpdated: "+str(lastUpdated))

      logger.info("bigcount: "+str(bigcount))
      logger.info("Items in LBIN: " + str(len(list(LBIN.keys()))))
      logger.info("Items in petlbin: " + str(len(list(petlbin.keys()))))
      logger.info("Items in armourlbin: " + str(len(list(armourlbin.keys()))))
      
      doEnded()

      try: #saving and organising data. calculating averages. not pretty.
        with open("cache/lbin.json", "w") as f:
          f.truncate(0)
          json.dump(LBIN, f, indent=4, ensure_ascii=False)
        with open("cache/nameLookup.json", "w") as f:
          f.truncate(0)
          json.dump(nameLookup, f, indent=4, ensure_ascii=False)
        with open("cache/skinLookup.json", "w") as f:
          f.truncate(0)
          json.dump(skinLookup, f, indent=4, ensure_ascii=False)
        with open("cache/GEM.json", "w") as f:
          f.truncate(0)
          json.dump(gemLookup, f, indent=4, ensure_ascii=False)
        with open("cache/heldItemLookup.json", "w") as f:
          f.truncate(0)
          json.dump(heldItemLookup, f, indent=4, ensure_ascii=False)
        with open("data/lbin.json", "r") as lbinfile:
          avglbin = json.load(lbinfile)
        for id in LBIN:
          if id in avglbin:
            if avglbin[id] > LBIN[id] * 2: #makes it easier for prices to drop than rise. its safer that way i hope.
              avglbin[id] = int(avglbin[id] - avglbin[id]/20 + LBIN[id]/20)
            elif avglbin[id] > LBIN[id] * 1.3:
              avglbin[id] = int(avglbin[id] - avglbin[id]/250 + LBIN[id]/250)
            else:
              avglbin[id] = int(avglbin[id] - avglbin[id]/1000 + LBIN[id]/1000)
          else:
            avglbin[id] = LBIN[id]
        with open("data/lbin.json", "w") as lbinfile:
          lbinfile.truncate(0)
          json.dump(avglbin, lbinfile, indent=2, ensure_ascii=False)

        """__--___---___--__PETS STUFF IS HERE____--___--___- """
        with open("data/pets/lbindata.pkl", "rb") as petlbinpkl:
          petlbindata = pickle.load(petlbinpkl)
        for petInfo in petlbin:
          if petInfo in petlbindata:
            petlbindata[petInfo] = int(petlbindata[petInfo] - petlbindata[petInfo]/500 + petlbin[petInfo]/500)
          else:
            petlbindata[petInfo] = petlbin[petInfo]
        with open("data/pets/lbindata.json", "w") as petlbinfile:
          petlbinfile.truncate(0)
          petlbinfile.write(str(petlbindata))
        with open("data/pets/lbindata.pkl", "wb") as petlbinpkl:
          petlbinpkl.truncate(0)
          pickle.dump(petlbindata, petlbinpkl)
        for item in petvolume:
          if petvolume[item] < 0:
            petvolume[item] = 0
          else:
            petvolume[item] = petvolume[item] - petvolume[item]/1440
        with open("data/pets/volume.json", "w") as f:
          f.truncate(0)
          f.write(str(petvolume))
        with open("data/pets/volume.pkl", "wb") as petvolumepkl:
          petvolumepkl.truncate(0)
          pickle.dump(petvolume, petvolumepkl)
        with open("data/pets/sold.json", "w") as soldfile:
          soldfile.truncate(0)
          soldfile.write(str(petavgsold))
        with open("data/pets/sold.pkl", "wb") as petssoldfile:
          petssoldfile.truncate(0)
          pickle.dump(petavgsold, petssoldfile)
        
        """__--___---___--ARMOUR STUFF IS HERE____--___--___- """
        #(add armour stuff here)
        with open("data/armour/lbindata.pkl", "rb") as armourlbinpkl:
          armourlbindata = pickle.load(armourlbinpkl)
        for armourInfo in armourlbin:
          if armourInfo in armourlbindata:
            armourlbindata[armourInfo] = int(armourlbindata[armourInfo] - armourlbindata[armourInfo]/500 + armourlbin[armourInfo]/500)
          else:
            armourlbindata[armourInfo] = armourlbin[armourInfo]
        with open("data/armour/lbindata.json", "w") as armourlbinfile:
          armourlbinfile.truncate(0)
          armourlbinfile.write(str(armourlbindata))
        with open("data/armour/lbindata.pkl", "wb") as armourlbinpkl:
          armourlbinpkl.truncate(0)
          pickle.dump(armourlbindata, armourlbinpkl)
        for item in armourvolume:
          if armourvolume[item] < 0:
            armourvolume[item] = 0
          else:
            armourvolume[item] = armourvolume[item] - armourvolume[item]/1440
        with open("data/armour/volume.json", "w") as f:
          f.truncate(0)
          f.write(str(armourvolume))
        with open("data/armour/volume.pkl", "wb") as armourvolumepkl:
          armourvolumepkl.truncate(0)
          pickle.dump(armourvolume, armourvolumepkl)
        with open("data/armour/sold.json", "w") as armoursoldpkl:
          armoursoldpkl.truncate(0)
          armoursoldpkl.write(str(armouravgsold))
        with open("data/armour/sold.pkl", "wb") as armoursoldfile:
          armoursoldfile.truncate(0)
          pickle.dump(armouravgsold, armoursoldfile)


        """__--___---___--OTHER STUFF IDK STUFF IS HERE____--___--___- """
        for item in volume:
          if volume[item] < 0:
            volume[item] = 0
          else:
            volume[item] = volume[item] - volume[item]/1440
        with open("data/volume.json", "w") as volumefile:
          volumefile.truncate(0)
          json.dump(volume, volumefile, indent=2, ensure_ascii=False)
        with open("data/sold.json", "w") as soldfile:
          soldfile.truncate(0)
          json.dump(avgsold, soldfile, indent=2, ensure_ascii=False)
        logger.info("Finished saving data, awaiting new data.")
      except Exception:
        logger.opt(exception=Exception).error("Something went wrong while saving average LBIN data.")
        #add failsafe here! wait where is the failsafe
    else:
      lastTry = milliTime()
      print("no new data.. trying again soon..")
  else:
    logger.info("retrying in 5 seconds")
    lastTry = milliTime() + 5000

try:
  main()
except Exception:
  logger.opt(exception=Exception).error("uncaught exception at some point in main()... (on first run)")

while True:
  if lastTry < milliTime() - 100:
    if (updateTime < milliTime() - 59_000): #starts trying slightly early.
      try:
        main()
      except Exception:
        logger.opt(exception=Exception).error("uncaught exception at some point in main()...")
    
