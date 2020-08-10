"""Utility functions for Legends discord bot."""
def format_time_delta(delta):
    """Create a pretty-prettification of datetime.timedelta."""
    if delta.total_seconds() < 0:
        return '! EVENT IS OVER !'
    output = ''
    days, remainder = divmod(delta.total_seconds(), 60*60*24)
    if days:
        output += '{} days, '.format(days)
    hours, remainder = divmod(remainder, 60*60)
    if hours:
        output += '{} hours, '.format(hours)
    minutes, remainder = divmod(remainder, 60)
    if minutes:
        output += '{} minutes, '.format(minutes)
    output += '{} seconds left...'.format(int(remainder))
    return output
