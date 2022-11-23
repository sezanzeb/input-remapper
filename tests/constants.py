# give tests some time to test stuff while the process
# is still running
EVENT_READ_TIMEOUT = 0.01

# based on experience how much time passes at most until
# the reader-service starts receiving previously pushed events after a
# call to start_reading
START_READING_DELAY = 0.05

# for joysticks
MIN_ABS = -(2**15)
MAX_ABS = 2**15
