// Ejecutar una vez en Windows. Archivos secretos ignorados; nunca imprimir tokens.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const dotenv=require('dotenv');
const archivo=path.join(__dirname,'.env');
const env=dotenv.parse(fs.readFileSync(archivo));
const privado=path.resolve(__dirname,'../../.dashcam-privado-20261028.json');
let config;
if(fs.existsSync(privado))config=JSON.parse(fs.readFileSync(privado,'utf8'));
else {
 config={backend:'https://dashguard-backend.onrender.com',device_id:env.DASHCAM_DEVICE_ID||'dashguard-pi-001',
   device_token:env.DASHCAM_DEVICE_TOKEN||crypto.randomBytes(32).toString('base64url'),
   owner_token:env.DASHCAM_OWNER_TOKEN||crypto.randomBytes(32).toString('base64url')};
 fs.writeFileSync(privado,JSON.stringify(config,null,2),{flag:'wx',mode:0o600});
}
const nuevos={DASHCAM_DEVICE_TOKEN:config.device_token,DASHCAM_OWNER_TOKEN:config.owner_token,DASHCAM_DEVICE_ID:config.device_id};
for(const [k,v] of Object.entries(nuevos)) {
 if(env[k] && env[k]!==v)throw Error('No se sobrescribe credencial existente: '+k);
 if(!env[k])fs.appendFileSync(archivo,`\n${k}=${v}\n`);
}
const exportar=path.join(__dirname,'.env.render');
const texto=Object.entries({SUPABASE_URL:env.SUPABASE_URL,SUPABASE_KEY:env.SUPABASE_KEY,...nuevos}).map(([k,v])=>`${k}=${v}`).join('\n')+'\n';
if(!fs.existsSync(exportar))fs.writeFileSync(exportar,texto,{flag:'wx',mode:0o600});
const soloNuevas=path.join(__dirname,'.env.render-nuevas');
if(!fs.existsSync(soloNuevas))fs.writeFileSync(soloNuevas,Object.entries(nuevos).map(([k,v])=>`${k}=${v}`).join('\n')+'\n',{flag:'wx',mode:0o600});
const rpi=path.resolve(__dirname,'../../.dashcam-rpi-20261028.json');
if(!fs.existsSync(rpi))fs.writeFileSync(rpi,JSON.stringify({backend:config.backend,device_id:config.device_id,device_token:config.device_token}),{flag:'wx',mode:0o600});
console.log('Configuracion privada preparada. Tokens distintos para dispositivo y propietario. Ninguna clave impresa.');
