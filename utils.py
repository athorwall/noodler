
# Parses a string of the form XX or XX:XX into seconds. Throws ValueError if string cannot be parsed.
def get_duration_in_seconds(duration_str):
    parts = duration_str.split(":")
    if len(parts) > 2:
        parts = parts[0:2]
    seconds = float(parts[-1])
    if len(parts) > 1:
        seconds += 60 * float(parts[0])
    return seconds

def seconds_to_time_str(seconds):
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    if minutes > 0:
        return "{:.0f}:{:05,.2f}".format(minutes, remaining_seconds)
    else:
        return "{:05,.2f}".format(remaining_seconds)

# Returns the duration in seconds represented by the given string, which must be in one of the following forms:
# - seconds, e.g. "5s, 10 seconds, 6sec, 8 s, 10"
# - bars, e.g. "5 bars"
# - beats, e.g. "10 beats"
# A duration with no units is considered to be in seconds already.
def get_duration_in_seconds(duration):
    numerical_prefix = ""
    i = 0
    while i < len(duration) and ((duration[i] >= '0' and duration[i] <= '9') or duration[i] == '.' or duration[i] == '-'):
        numerical_prefix += duration[i]
        i += 1
    qty = float(numerical_prefix)
    units = duration[i:].strip()
    if units == "" or units == "s" or units == "sec" or units == "seconds":
        return qty

