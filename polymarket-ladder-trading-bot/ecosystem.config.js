module.exports = {
  apps: [
    {
      name: "liquidity-maker",
      script: ".venv/bin/polybot5m",
      args: "run",
      cwd: "/root/polymarket-market-maker",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      env: {
        PATH: "/root/polymarket-market-maker/.venv/bin:" + process.env.PATH,
      },
    },
  ],
};
