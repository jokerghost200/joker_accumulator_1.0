import math
rate = 0.05
tp = 0.25
ticks = math.ceil(math.log(1 + tp) / math.log(1 + rate))
print(f'Rate: {rate}, Ticks: {ticks}')
