"""
Tools for computing periods with various methods
"""
import contextlib
import numpy
from IPython import parallel

import multiband_LS
from multiband_LS.data import fetch_light_curves
from multiband_LS.memoize import CacheResults


def parallelize(func, *client_args, **client_kwargs):
    @contextlib.wraps(func)
    def wrapper(lcids, *args, **kwargs):
        client = parallel.Client(*client_args, **client_kwargs)
        print("client ids:", client.ids)

        dview = client.direct_view()
        with dview.sync_imports():
            import numpy
            import multiband_LS
            from multiband_LS.memoize import CacheResults
            from multiband_LS.data import fetch_light_curves

        # Make sure the light curves are fetched before parallelizing,
        # otherwise this may lead to parallel file downloads!
        client[0].execute('fetch_light_curves()')

        lbv = client.load_balanced_view()
        lbv.block = False

        lcid_batches = [[lcid] for lcid in lcids]

        results = lbv.map(func, lcid_batches, args=args, kwargs=kwargs)

        from time import time
        t0 = time()
        for i, result in enumerate(results):
            print("{0}/{1} : {2}".format(i + 1, len(results), result))
            print("     elapsed: {0:.0f} sec".format(time() - t0))
        return numpy.concatenate(results)
    return wrapper


def best_period_Multiband(lcid, rrlyrae,
                          Nterms_base=1, Nterms_band=0):
    t, y, dy, filts = rrlyrae.get_lightcurve(lcid, return_1d=True)
    ls = multiband_LS.LombScargleMultiband(Nterms_base=Nterms_base,
                                           Nterms_band=Nterms_band)
    ls.optimizer.period_range = (0.2, 1.2)
    ls.fit(t, y, dy, filts)
    return ls.best_period


def periods_Multiband(lcids, Nterms_base=1, Nterms_band=0,
                      func=best_period_Multiband):
    cachedir = 'results_multiband_{0}_{1}'.format(Nterms_base, Nterms_band)
    cache = CacheResults(cachedir, verbose=True)
    rrlyrae = fetch_light_curves()
    results = cache.call_iter(func, lcids,
                              args=(rrlyrae, Nterms_base, Nterms_band))
    return numpy.asarray(results)


def best_period_SuperSmoother(lcid, rrlyrae, filt='g'):
    t, y, dy, filts = rrlyrae.get_lightcurve(lcid, return_1d=True)
    t, y, dy = (x[filts == filt] for x in (t, y, dy))
    ssm = multiband_LS.SuperSmoother()
    ssm.optimizer.period_range = (0.2, 1.2)
    ssm.fit(t, y, dy)
    return ssm.best_period


def periods_SuperSmoother(lcids, filt='g', func=best_period_SuperSmoother):
    cachedir = 'results_supersmoother_{0}'.format(filt)
    cache = CacheResults(cachedir, verbose=True)
    rrlyrae = fetch_light_curves()
    results = cache.call_iter(func, lcids, args=(rrlyrae, filt))
    return numpy.asarray(results)


periods_Multiband_parallel = parallelize(periods_Multiband)
periods_SuperSmoother_parallel = parallelize(periods_SuperSmoother)

if __name__ == '__main__':
    rrlyrae = fetch_light_curves()
    ids = list(rrlyrae.ids)[:10]
    print(periods_Multiband_parallel(ids))
    print(periods_SuperSmoother_parallel(ids))
