module.exports = {
  apps: [
    {
      name: 'nestjs',
      script: 'dist/main.js',
      cwd: __dirname,
      instances: 4,
      exec_mode: 'cluster',
    },
  ],
};
