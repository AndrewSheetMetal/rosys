import logging.config

import icecream


def setup():
    icecream.install()

    config = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'default': {
                'format': '%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': 'INFO',
                'stream': 'ext://sys.stdout'
            },
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console'],
                'level': 'WARN'
            },
            'rosys': {
                'level': 'DEBUG'
            },
            'rosys.ota': {
                'level': 'WARN'
            },
            'hello_bot': {
                'level': 'DEBUG'
            },
        },
    }

    logging.config.dictConfig(config)
