import subprocess
import logging
import logging.handlers


def notifier(message='', title=None, subtitle=None, group=None, sound=None):
    """ Use `terminal-notifier` to post a message."""
    command = [
        '/usr/local/bin/terminal-notifier',
        '-message', message,
    ]
    if title is not None:
        command.extend(['-title', title])
    if subtitle is not None:
        command.extend(['-subtitle', subtitle])
    if group is not None:
        command.extend(['-group', group])
    if sound is not None:
        command.extend(['-sound', sound])

    subprocess.run(command)


class NotifierHandler(logging.Handler):
    """Defines a logging handler that will log a message to the terminal-notifier."""
    def emit(self, record):
        notifier(message=record.getMessage(),
                 title='Notifier Handler',
                 subtitle=record.levelname,
                 sound="Morse")


def scioto_logger():
    """ Returns a logging handler for my local networking logging feature."""
    return logging.handlers.SocketHandler(
        'localhost',
        logging.handlers.DEFAULT_TCP_LOGGING_PORT
    )


if __name__ == '__main__':
    # Do a quick test of these features.
    import datetime

    socket_handler = logging.handlers.SocketHandler(
        'localhost',
        logging.handlers.DEFAULT_TCP_LOGGING_PORT
    )

    logging.basicConfig(
        level=logging.INFO,
        handlers=[scioto_logger(), NotifierHandler()]
    )

    msg = f"Time: {datetime.datetime.today()}"

    logging.info(f"Notifier/Logging test: {msg}")
    notifier(message=msg,
             title='My title',
             subtitle='My subtitle',
             group='My group',
             sound='Sosumi',
             )

