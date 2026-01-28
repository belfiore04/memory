module.exports = {
    apps: [
        {
            name: 'memory-api',
            script: '/opt/homebrew/bin/python3.11',
            args: '-m uvicorn main:app --host 0.0.0.0 --port 8000',
            cwd: '/Users/jinyijun/Documents/code/memory',
            env: {
                INCLUDE_EPISODES: 'true'
            },
            autorestart: true,
            max_restarts: 50,
            restart_delay: 5000,
            max_memory_restart: '1G',
            log_date_format: 'YYYY-MM-DD HH:mm:ss',
            error_file: './logs/pm2-error.log',
            out_file: './logs/pm2-out.log',
            merge_logs: true,
            watch: false,
            kill_timeout: 3000,
        },
        {
            name: 'ngrok',
            script: 'ngrok',
            args: 'http 8000',
            cwd: '/Users/jinyijun/Documents/code/memory',
            autorestart: true,
            max_restarts: 100,
            restart_delay: 3000,
            log_date_format: 'YYYY-MM-DD HH:mm:ss',
            error_file: './logs/ngrok-error.log',
            out_file: './logs/ngrok-out.log',
            merge_logs: true,
            watch: false,
            kill_timeout: 3000,
        },
        {
            name: 'scheduler',
            script: '/opt/homebrew/bin/python3.11',
            args: 'scheduler.py',
            cwd: '/Users/jinyijun/Documents/code/memory',
            autorestart: true,
            max_restarts: 50,
            restart_delay: 5000,
            log_date_format: 'YYYY-MM-DD HH:mm:ss',
            error_file: './logs/scheduler-error.log',
            out_file: './logs/scheduler-out.log',
            merge_logs: true,
            watch: false,
            kill_timeout: 3000,
        }
    ]
}
