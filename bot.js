const mineflayer = require('mineflayer')
const mineflayerViewer = require('prismarine-viewer').mineflayer


const bot = mineflayer.createBot({
  host: 'hypixel.net', // minecraft server ip
  username: 'tla_', // minecraft username
  auth: 'microsoft', // for offline mode servers, you can set this to 'offline'
  version: "1.8.9"             // only set if you need a specific version or snapshot (ie: "1.8.9" or "1.16.5"), otherwise it's set automatically
})

bot.on('chat', (username, message) => {
  if (username === bot.username) return
  console.log(`${username}: ${message}`)
})

bot.once('spawn', () => {
  console.log("He has spawned in.")
  mineflayerViewer(bot, { port: 3007, firstPerson: false })
})

// Log errors and kick reasons:
bot.on('kicked', console.log)
bot.on('error', console.log)