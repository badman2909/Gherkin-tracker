const { spawn } = require('child_process');
const server = spawn('node', ['server.js']);

server.stdout.on('data', (data) => {
  console.log(stdout: );
});

server.stderr.on('data', (data) => {
  console.error(stderr: );
});

server.on('close', (code) => {
  console.log(child process exited with code );
});
