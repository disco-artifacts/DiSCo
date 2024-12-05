import time

__start_time = -1
__end_time = -1

def print_start():
    global __start_time
    __start_time = time.time()
    print_verbose("start:%s"%(str(__start_time)), padding="=")

def print_end():
    global __start_time, __end_time
    __end_time = time.time()
    print_verbose("end:%s, cost:%ds"%(str(__end_time), __end_time - __start_time), padding="=")

def print_verbose(information:str, length:int=70, padding:str=" ", symbol:str='*'):
    # print(symbol*length + "\n" + symbol + information.center(length-2," ") + symbol + "\n" + symbol + (str(time_cost) + "s").center(length-2," ") + symbol)
    print(symbol + information.center(length-2,padding) + symbol)