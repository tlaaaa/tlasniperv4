const http = require('http');
const WebSocketServer = require('websocket').server;
const fs = require('fs')

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
    fs.readFile('flips.json', 'utf8', function(err, data){
      if (err) {
        return console.error(err);
      }
      if (data != "") {
        data = JSON.parse(data)
        wsServer.broadcast(JSON.stringify(data))
        fs.truncate("flips.json", 0, function() {
          console.log(data)
        })
      }
});
}

setInterval(checkFile, 10);