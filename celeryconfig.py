import os


# One always get a string from env and need to convert to bool.
def get_bool_from_env(key, default):
    try:
        val = os.environ[key]
    except KeyError:
        return default
    else:
        if val == "True":
            return True
        elif val == "False":
            return False
        else:
            raise ValueError(
                "'%s' value should be string 'False' or 'True' (was '%s')"
                % (key, val)
            )


BROKER_URL = os.environ.get('BROKER_URL')
BROKER_USE_SSL = get_bool_from_env('BROKER_USE_SSL', False)
CELERY_IMPORTS = ('worker',)
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ('json',)
CELERYD_FORCE_EXECV = True
CELERYD_MAX_TASKS_PER_CHILD = 1
CELERYD_PREFETCH_MULTIPLIER = 1
CELERYD_CONCURRENCY = 1
