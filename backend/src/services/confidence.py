"""基于实测差错数的有限总体无放回单侧置信上界。

复核结束后，总体规模 N、实检样本 n、实测差错 d 均为已知量，
不再沿用抽样设计阶段的预估差错率/假设 D。

采用 Clopper–Pearson 型超几何口径：对总体差错总数 D 求最小整数 U，
使 P_{N,U,n}(X <= d) <= alpha，即若总体真有 U 份差错，
抽到的差错数不超过实测 d 的概率不高于 alpha（单侧 1-alpha 置信）。

边界：
- d=0 时同样计算（零差错照算），U 为满足 P(X=0)=C(N-U,n)/C(N,n) <= alpha 的最小 U；
- n=N 全检时总体差错数即观测值，U=d（含 d=0 时 U=0）；
- n=0 时无样本信息，上界为 N；未全检而样本全错（d=n<N）时无法排除其余皆错，U=N；
- 1-alpha 置信度固定 95%，alpha=0.05。

组合数为 Python 任意精度整数，概率比较用 Fraction 整数交叉相乘，避免浮点相消。
"""
import math
from fractions import Fraction

ALPHA_95 = Fraction(5, 100)


def _cdf_le(N, D, n, d):
    """P_{N,D,n}(X <= d)，任意精度 Fraction。"""
    total = math.comb(N, n)
    cum = 0
    upper = min(d, D, n)
    for k in range(upper + 1):
        if n - k > N - D:
            continue
        cum += math.comb(D, k) * math.comb(N - D, n - k)
    return Fraction(cum, total)


def upper_error_bound(N, n, d, alpha=ALPHA_95):
    """返回总体差错总量的 1-alpha 单侧置信上界（整数份数）。"""
    if not all(isinstance(v, int) for v in (N, n, d)):
        raise ValueError("N,n,d 必须为整数")
    if N < 1 or not 0 <= n <= N or not 0 <= d <= n:
        raise ValueError("N,n,d 取值范围无效")
    if n == 0:
        return N
    if n == N:
        # 全检：总体差错数即实测值，无推断不确定性
        return d
    if d >= n:
        # 未全检而样本全错：无法排除未检部分皆错
        return N
    # D <= d 时 P(X<=d)=1，必然不满足；从 d+1 起二分。
    lo, hi = d + 1, N
    while lo < hi:
        mid = (lo + hi) // 2
        if _cdf_le(N, mid, n, d) <= alpha:
            hi = mid
        else:
            lo = mid + 1
    return lo


def stratum_error_summary(stratum_rows):
    """按风险层汇总实检结果并计算置信上界。

    入参为每层的 dict：stratum / N(层总体) / n(实检份数) / d(实测差错份数)，
    返回原结构并附加 upper_95 与 error_rate_upper（上界对应总体差错率）。
    """
    out = []
    for row in sorted(stratum_rows, key=lambda r: r["stratum"]):
        N, n, d = row["N"], row["n"], row["d"]
        upper = upper_error_bound(N, n, d)
        out.append({
            **row,
            "upper_95": upper,
            "error_rate_upper": round(upper / N, 6),
            "observed_rate": (d / n) if n else 0.0,
        })
    return out
