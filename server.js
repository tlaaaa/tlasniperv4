const http = require('http');
const WebSocketServer = require('websocket').server;
const fs = require('fs')

const { Client, Events, GatewayIntentBits, EmbedBuilder } = require('discord.js');

const client = new Client({ intents: [GatewayIntentBits.Guilds] });
var sendChannel

client.on('ready', client => {
  console.log(`Ready! Logged in as ${client.user.tag}`);
  var startedEmbed = new EmbedBuilder().setColor(0x000000).setTitle('tlasniperv4 is now online!').setTimestamp()
  sendChannel = client.channels.cache.get('1040154468370632714')
  sendChannel.send({ embeds: [startedEmbed] });
  setInterval(checkFile, 10);
});

var lastUpdate = 0;

function writeHtml(outputStream) {
    const inputStream = fs.createReadStream('index.html')

    inputStream.pipe(outputStream)

    outputStream.on('finish', () => {
        console.log('served https')
        outputStream.end();
    })
    outputStream.on('error', (e) => {
        console.error('errors', e)
        outputStream.end();
    })
}

const server = http.createServer(function (req, res) {
  res.writeHead(200, {'Content-Type': 'text/html'});
  writeHtml(res)
})
server.listen(3000);
const wsServer = new WebSocketServer({
    httpServer: server
});

const blacklist = ["Moody Grapple", "Abiphone", "Crab Hat", "Century Cake", "Wand of Strength", "Ocelot", "Mender Crown", "Red Snubfin", " Skin", "Griffin Upgrade", "Beastmaster"]

wsServer.on('request', function(request) {
    console.log("WS Connected")
  
    const connection = request.accept(null, request.origin);
    connection.on('message', function(message) {
      console.log('Received Message:', message.utf8Data);
    });
    connection.on('close', function(reasonCode, description) {
        console.log('Client has disconnected. '+description);
    });
});

function checkFile() {
  if (Date.now() > lastUpdate + 59000) {
    fs.readFile('flips.json', 'utf8', function(err, data){
      if (err) {
        return console.error(err);
      }
      if (data != "") {
        data = JSON.parse(data)
        tosend = []
        fs.truncate("flips.json", 0, function() {
          //console.log(data)
          lastUpdate = Date.now()
        })
        var embed = new EmbedBuilder().setColor(0x000000).setTitle('omg new flips').setTimestamp()
        data.flips.forEach((flip) => {
            if (flip.target < 10000000){
              var profit = (flip.target - flip.startingBid) - flip.target*0.02
            } else if (flip.target < 100000000){
              var profit = (flip.target - flip.startingBid) - flip.target*0.03
            } else {
              var profit = (flip.target - flip.startingBid) - flip.target*0.035
            }
            profit = Math.round(profit/1000)*1000
            if (flip.notes != "") {
              embed.addFields({ name: flip.itemName, value: '`/viewauction '+flip.id+"`\nPrice: "+flip.startingBid.toString()+"\nTarget: "+flip.target.toString()+"\nEst. Profit: "+profit.toString()+"\nNotes: "+flip.notes, inline: false })
            }
            else {
            	embed.addFields({ name: flip.itemName, value: '`/viewauction '+flip.id+"`\nPrice: "+flip.startingBid.toString()+"\nTarget: "+flip.target.toString()+"\nEst. Profit: "+profit.toString(), inline: false })
            }
            if (profit > 0 && profit/flip.target > 0){
              send = true
              blacklist.forEach((blacklisted) => {
                if (flip.itemName.includes(blacklisted)) {
                  send = false
                }
              })
              if (send) {
            tosend.push(flip)
              }
            }
        });
        wsServer.broadcast(JSON.stringify({"flips": tosend}))
        console.log(tosend)
        try {
        sendChannel.send({ embeds: [embed] });
        } catch (error) {
          console.log("uh oh")
          console.log(error)
        }
      }
});
}
}

client.login(process.env.TOKEN);
