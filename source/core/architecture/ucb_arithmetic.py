# Explicit integer UCB profile; the legacy binary64 selection stays available.
# SPDX-License-Identifier: MIT
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import math
from numbers import Integral

PROFILE='ucb_q32_ln256_v1'


def logarithm_table():
    with localcontext() as context:
        context.prec=80
        return [int(((Decimal(1)+Decimal(i)/256).ln()*2**48).to_integral_value(rounding=ROUND_HALF_EVEN)) for i in range(257)]


LOG_TABLE=logarithm_table()
LN2=LOG_TABLE[256]


def round_divide(numerator, denominator):
    quotient,remainder=divmod(numerator,denominator)
    return quotient+int(2*remainder>denominator or (2*remainder==denominator and quotient%2))


def log_q48(visits):
    leading=visits.bit_length()-1
    normalized=(visits << 24) >> leading
    index=(normalized >> 16)&255
    fraction=normalized&65535
    return leading*LN2+LOG_TABLE[index]+round_divide((LOG_TABLE[index+1]-LOG_TABLE[index])*fraction,65536)


def score_q32(parent_visits, child_visits, child_value, exploration):
    for visits in (parent_visits,child_visits):
        if isinstance(visits,bool) or not isinstance(visits,Integral) or not 1<=visits<2**32:
            raise ValueError('Visited UCB operands require unsigned nonzero 32-bit counts')
    if child_visits>parent_visits: raise ValueError('Child visits exceed parent visits')
    if not math.isfinite(child_value) or not 0<=child_value<=child_visits or math.copysign(1.0,child_value)<0:
        raise ValueError('Value sum must be finite and within the visit count')
    value_q17=float(child_value)*131072
    if not value_q17.is_integer(): raise ValueError('Value sum is not exactly Q17')
    if not math.isfinite(exploration) or not 0<=exploration<=8:
        raise ValueError('Exploration must be finite and between zero and eight')
    coefficient=round(exploration*2**32)
    mean=round_divide(int(value_q17)<<31,int(child_visits))
    ratio=round_divide(log_q48(int(parent_visits)),int(child_visits))
    root=math.isqrt(ratio<<48)
    return round_divide(((2**48-mean)<<32)+root*coefficient,2**48)


def score(parent_visits, child_visits, child_value, exploration):
    return score_q32(parent_visits,child_visits,float(child_value),exploration)/2**32


def next_choice(state):
    value=state or 0x6d2b79f5
    value=(value ^ (value<<13))&0xffffffff
    value=value ^ (value>>17)
    return (value ^ (value<<5))&0xffffffff
