#! /usr/bin/python2.7
# -*- coding: utf-8 -*-

import warnings
import re
import numpy as np
from itertools import izip, count # izip for maximum efficiency: http://stackoverflow.com/questions/176918/finding-the-index-of-an-item-given-a-list-containing-it-in-python

from errval import *
from errvallist import *
from stderrval import *

'''
functions for dealing with lists containing errvals
not necessarily errvallists
'''

# convenience functions so you don't have to care about the input
# but mind you: if the input isn't an errvallist, this issues an expensive and probably unnecessary operation!
def values(errvall):
    if not isinstance(errvall,errvallist):
        errvall = errvallist(errvall)
    return errvall.v()
def errors(errvall):
    if not isinstance(errvall,errvallist):
        errvall = errvallist(errvall)
    return errvall.e()
def tuples(errvall):
    return zip(values(errvall),errors(errvall))

def str2errvallist(strng):
    p = re.compile('errval\((-?\d*.\d*e?-?\d*?),(\d*.\d*e?-?\d*?),?(errvalmode)?\)') # note, errvalmode is detected, but will throw an error!
    lst = re.findall(p,strng) # returns list of tuples of length 2 or 3, errval knows how to handle tuple input
    return errvallist(lst)
    

def _find_index_iteratively(array,value,low=None,high=None):
    '''
    same as find_index() but the value has to be exact
    [low,high] constrains search if approx position in the array is known already

    example:
    a = [1,2,3,4,5,6,7,8,9,0]
    it = find_index_iter(a,4)
    print it, (it==3)
    it = find_index_iter(a,8,high=6)
    print it, (it==None)
    it = find_index_iter(a,8,high=7)
    print it, (it==7)
    it = find_index_iter(a,0,low=7)
    print it, (it==9)
    '''
    if low==None: low=0
    if high==None: high=len(array)-1

    it = low
    for search in xrange(high-low+1):
    # one more iteration than range: to get last iteration as well.
    # if the value is found, this loop should break
    # if it doesn't the last +=1 is executed, which we can detect.
        if array[it]==value: break
        it += 1
    if it==high+1: it=None # not found; loop didn't break
    return it

def _find_closest_fooval(L,foo,index=False):
    # return value from list L,
    # whose value is closest to the result of function foo 
    # index = True or False, whether to return the corresponding index
    if isinstance(L,errvallist):
        v = values(L)
    else:
        v = L
    i = _find_index_iteratively(v,foo(v))
    if index: return L[i], i
    else: return L[i]

def max(evl,index=True):
    # index = True or False, whether to return the corresponding index
    return _find_closest_fooval(evl,np.max,index)
def min(evl,index=True):
    # index = True or False, whether to return the corresponding index
    return _find_closest_fooval(evl,np.min,index)

def wmean(evlist):
    '''
    weighted mean

    sigma_<x>^2 = sum(1/sigma_i^2)
    <x> = sum(x_i/sigma_i^2)/sigma_<x>^2
    '''
    printmode = evlist[0].printout()
    vals = values(evlist)
    #print vals
    errs = errors(evlist)
    #print errs
    N = len(evlist)
    sig_x = np.sum([1.0/si**2 for si in errs])
    sum_x = np.sum([vals[i]*1.0/errs[i]**2 for i in range(N)])
    return errval(sum_x*1.0/sig_x,1.0/np.sqrt(sig_x),printmode)
    
def interp(v,evxy0,evxy1):
    '''
    linear interpolation between two points
    evxy0 (evxy1) is expected to be a tuple
    representing the x and y value of the
    point to the left (right) of value v
    otherwise it's an extrapolation - proceed with caution!

    Basic idea (for values between v \in [0,1]):
        y = y0 + v*(y1-y0)
    But v is not bound to [0,1], so we have to renormalize:
        v' = (v-x0)/(x1-x0).
    This makes it implicitly clear that we expect x1>x0,
    so, order your input properly!
    We end up:
        y = y0 + (v-x0)/(x1-x0)*(y1-y0).
    '''
    if not isinstance(evxy0,tuple) or not isinstance(evxy1,tuple):
        raise TypeError,\
             'Boundary required as tuple, {0} and {1} given'.format(
                type(evxy0),type(evxy1))
    # if input can be handled with pre-existing functions:
    if not isinstance(evxy0[0],errval) and \
        not isinstance(evxy0[1],errval) and \
        not isinstance(evxy1[0],errval) and \
        not isinstance(evxy1[1],errval):
        return np.interp(v,evxy0,evxy1)
    # ok, at least one of the inputs is errval; worth the time:
    # make sure every entry is indeed errval
    # (because lazy, the x-values don't need to have an error,
    # in fact, if they do this error will be lost)
    x0, y0 = errval(evxy0[0]), errval(evxy0[1])
    x1, y1 = errval(evxy1[0]), errval(evxy1[1])

    if x1.v()==x0.v(): return evxy0[1] # they're the same, cannot work with it
    scaling = float(v-x0.v())/(x1.v()-x0.v())
    y = y0.v() + scaling*(y1.v()-y0.v())
    ye = y0.e() + scaling*abs(y1.e()-y0.e())
    #scalingy = (y-y0.v())/(y1.v()-y0.v())
    #xe = scalingy*abs(x1.e()-x0.e())
    return errval(y,ye)

def interplist(v,evx,evy, warning_on_extrapolation_attempt=True):
    '''
    v a value corresponding to evx for which we look its counterpart among evy
    evx must be an ordered (errval,)list or a numpy.ndarray
    evy must be a errvallist
    when v is outside the coverage of evx we raise an IndexError if error_on_extrapolation_attempt
    otherwise the edge value is assumed
    (careful, your data may then suggest a trend simply because one of the inputs got capped along the way!)
    '''
    if not isinstance(evx,(list,tuple,errvallist,np.ndarray)):
        raise TypeError, 'evx is of unexpected type: {0}'.format(type(evx))
    if not isinstance(evy,errvallist):
        raise TypeError, 'This function is for errvallists, try np.interp'
    if isinstance(evx,errvallist):
        evx = evx.v() # errval has only one-dimensional error
    if isinstance(v,errval): v = v.v()
    i0 = np.sum([e<=v for e in evx])
    nevx, nevy = map(len,[evx,evy])
    if warning_on_extrapolation_attempt:
        if i0==0:
            warnings.warn('Requested value ({}) is *below* interpolation, results won\'t make sense. Set error_on_extrapolation_attempt=False in order to ignore this and clip.'.format(v))
        elif i0==nevx:
            warnings.warn('Requested value ({}) is *above* interpolation, results won\'t make sense. Set error_on_extrapolation_attempt=False in order to ignore this and clip.'.format(v))
    # if outside interpolation values, take top or bottom value.
    try:
        xy0 = (evx[np.max([i0-1,0])],evy[np.max([i0-1,0])])
        xy1 = (evx[np.min([i0,nevx-1])],evy[np.min([i0,nevy-1])])
    except IndexError, e:
        print '\nIssued with index',i0,'on list lengths',[nevx,nevy],'\n'
        raise IndexError, e
    return interp(v,xy0,xy1)

def reorder(evlist, instr):
    return errvallist([evlist[i] for i in instr])

def sorting_instr(evlist):
    #http://stackoverflow.com/questions/176918/finding-the-index-of-an-item-given-a-list-containing-it-in-python
    #http://stackoverflow.com/questions/479897/how-do-you-remove-duplicates-from-a-list-in-python-if-the-item-order-is-not-impo
    v = sorted(values(evlist))
    ret = []
    for k in v:
        ret.extend([i for i, j in izip(count(), evlist.v()) if j == k])
    return ret

# -----------------------------------------------------------------------

def _linregA(B, xys):
    '''
    help function for linreg()
    xys = zip(xi, yi, si) values and uncertainties in tuple-form for easier access
    B from y=A+Bx
    '''
    xi, yi, si = zip(*xys)
    n = len(xys)
    isi = np.sum([1.0/ssi**2 for ssi in si]) # sum of inverse error squares
    A = 1.0/isi * np.sum([(yi[i]-B*xi[i])/si[i]**2 for i in xrange(n)])
    return A

def _linregB(xys):
    '''
    help function for linreg()
    xys = zip(xi, yi, si) values and uncertainties in tuple-form for easier access
    '''
    xi, yi, si = zip(*xys)
    n = len(xys)
    isi = np.sum([1.0/ssi**2 for ssi in si]) # sum of inverse error squares
    xiyisi2 = np.sum([xi[i]*yi[i]*1.0/si[i]**2 for i in xrange(n)])
    xisi2 = np.sum([xi[i]*1.0/si[i]**2 for i in xrange(n)])
    yisi2 = np.sum([yi[i]*1.0/si[i]**2 for i in xrange(n)])
    xi2si2 = np.sum([xi[i]**2*1.0/si[i]**2 for i in xrange(n)])

    B = (isi*xiyisi2 - xisi2*yisi2)*1.0/(isi*xi2si2 - xisi2**2)
    return B

def linreg(xi,yi,si,overwrite_zeroerrors=False):
    '''
    xi the x values,
    yi the y values,
    si the uncertainties (/errors) attached to yi
    overwrite0errors = True or False, if one of the si's is ==0, the function cannot work b/c we divide through si
        True: overwrite those 0 entries with 0.1*min of residual error entries
        False: raise a ValueError, because this function cannot function with a 0...!

    returns coefficients A and B for y=A+Bx

    Uncertainties in x are ignored.
    Those in y are assumed to be Gaussian (denoted s_i).
    In this case we have to minimize
    \Chi^2 = \sum\limits_{i=1}^n \frac{[y_i - (A+Bx_i)]^2}{2s_i^2} = minimum
    i.e. \frac{\partial \Chi^2}{\partial A} = 0 = \frac{\partial \Chi^2}{\partial B}

    For the error value attached to A and B we use the so called Jackknife approach,
    see
        B. Efron, G. Gong, A Leisurely Look at the Bootstrap, the Jachknife and Cross-Validation,
        The American Statistician, Vol 37, No 1 (Feb 1983), pp. 36-48.
    We could -- in principle -- use the uncertainties handed in
    with the usual error propagation:
    s_A = \sqrt{ \sum\limits_i s_i^2 (\frac{\partial A}{\partial y_i})^2 }
    but this gives a very ugly formula.
    So I won't even try to type it in correctly.
    '''
    n = len(yi)
    if len(xi)!=n:
        raise ValueError, 'Inputs cannot be brought together with lengths {}, {}'.format(len(xi),n)

    if 0 in si:
        valid_errors = np.array(si)!=0
        if overwrite_zeroerrors and np.sum(valid_errors)>0: # there is at least one valid error
            min_valid = np.min(si[valid_errors])
            for i in xrange(n):
                if si[i]==0: si[i]=min_valid*0.1
        else:
            raise ValueError, 'This function cannot operate with 0 error entries.'

    xys = zip(xi,yi,si)

    B = _linregB(xys)
    A = _linregA(B, xys)

    # attaching errors with Jackknife:
    #  B. Efron, G. Gong, A Leisurely Look at the Bootstrap, the Jachknife and Cross-Validation,
    #  The American Statistician, Vol 37, No 1 (Feb 1983), pp. 36-48
    # for a separate view at this method see also
    # https://github.com/stefantkeller/STK_py_generals/blob/master/jackknife_bootstrap.py

    # this makes sense only iff there are enough data available
    # how much 'enough' means is difficult to say
    # but clearly more than two!
    if len(xi)<=2:
        sigma_A = np.nan
        sigma_B = np.nan
        return errval(A,sigma_A), errval(B,sigma_B)
        
        
    # only evaluate if there are more than two data points available

    A_, B_ = [], []
    for k in xrange(n):
        xys_ = [xys[j] for j in xrange(n) if j!=k]
        b_ = _linregB(xys_)
        a_ = _linregA(b_, xys_)
        A_.append(a_)
        B_.append(b_)
    Adot,Bdot = map(np.mean,[A_,B_])

    sigma = lambda X,Xdot: (n-1)**0.5*np.std([x-Xdot for x in X], ddof=0)
    sigma_A = sigma(A_,Adot)
    sigma_B = sigma(B_,Bdot)

    return errval(A,sigma_A), errval(B,sigma_B)
    
    

