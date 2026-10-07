const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const files=['index.html','og-shift.png'];
const types={'.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.mp3':'audio/mpeg','.html':'text/html; charset=utf-8'};
// voice/ と img/ の中のファイルも配る（それ以外は 404）
const allowed=f=>files.includes(f)||/^(voice|img)\/[\w-]+\.(mp3|png|jpg|webp)$/.test(f);
http.createServer((req,res)=>{const file=decodeURIComponent(req.url.split('?')[0].slice(1))||'index.html';if(!allowed(file)||!fs.existsSync(path.join(__dirname,file))){res.writeHead(404);return res.end('Not found');}res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');res.setHeader('Cache-Control','no-store');res.end(fs.readFileSync(path.join(__dirname,file)));}).listen(+process.env.PORT||8088,'127.0.0.1',()=>console.log('http://127.0.0.1:'+(+process.env.PORT||8088)));
