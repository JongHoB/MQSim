#!/usr/bin/env python3
import os
import re
import math
from typing import Optional
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SUMMARY_CSV = "mqsim_summary.csv"
OUTPUT_ROOT = "plots"  # 이 아래에 cache/ioqd/channels/ways 폴더 생김


def build_dataframe(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # synthetic + tpcc 통합 workload 이름
    def workload_label(row):
        if row["access_pattern"] == "tpcc":
            return "tpcc"
        else:
            return f"{row['access_pattern']}_{row['block_size']}"

    df["workload"] = df.apply(workload_label, axis=1)

    # "0MB", "128MB", "256MB", "1GB" → MiB 숫자
    def parse_cache_size(s):
        if pd.isna(s):
            return math.nan
        m = re.match(r"(\d+)(MB|GB)", str(s))
        if not m:
            return math.nan
        v = int(m.group(1))
        u = m.group(2)
        if u == "MB":
            return float(v)
        elif u == "GB":
            return float(v * 1024)
        return math.nan

    if "cache_size" in df.columns:
        df["cache_size_MiB"] = df["cache_size"].apply(parse_cache_size)
    else:
        df["cache_size_MiB"] = math.nan

    return df


def plot_metric_vs_param(df: pd.DataFrame,
                         param_col: str,
                         metric_col: str,
                         outdir: str,
                         title_prefix: Optional[str] = None) -> None:
    """
    param_col: 'cache_size_MiB' / 'io_queue_depth' / 'channels' / 'chips_per_channel'
    metric_col: 위에서 지정한 metric 이름들
    """

    # 필요한 컬럼+workload가 비어있지 않은 row만 사용
    use = df.dropna(subset=[param_col, metric_col, "workload"]).copy()
    if use.empty:
        print(f"[skip] {param_col}, {metric_col} 에 해당하는 데이터가 없음")
        return

    # x축 이름
    if param_col == "cache_size_MiB":
        x_label = "DRAM cache size (MiB)"
    elif param_col == "io_queue_depth":
        x_label = "I/O queue depth"
    elif param_col == "channels":
        x_label = "Number of channels"
    elif param_col == "chips_per_channel":
        x_label = "Chips per channel (ways)"
    else:
        x_label = param_col

    # title에 쓸 이름
    labels = {
       "host_BW_MiB_per_s" : "Host Bandwidth (MiB/s)",
        "host_IOPS" : "Host IOPS",
        "host_E2E_Latency_ms_assuming_us" : "Host E2E Latency (ms)",
        "tsu_User_Transactions_Enqueued" : "TSU User Transactions Enqueued",
        "ftl_Total_Flash_Read_CMD" : "FTL Total Flash Read CMD",
        "ftl_Total_Flash_Program_CMD" : "FTL Total Flash Program CMD",
        "ftl_Total_Flash_Erase_CMD" : "FTL Total Flash Erase CMD",
        "ftl_CMT_Hit_Rate" : "FTL CMT Hit Rate",
        "ftl_Total_GC_Executions" : "FTL Total GC Executions",
        "chip_Avg_Fraction_Idle" : "Chip Avg Fraction Idle",
        "chip_Avg_Fraction_DataXfer" : "Chip Avg Fraction DataXfer",
        "chip_Avg_Fraction_Exec" : "Chip Avg Fraction Exec",
        "energy_Energy_per_IO_Index" : "Power(Energy/IO)", 
    }
    y_label = labels[metric_col] if metric_col in labels else metric_col


    # 정렬을 위해 float로 변환
    use["x"] = use[param_col].astype(float)
    use = use.sort_values(["workload", "x"])

    plt.figure()
    for workload, sub in use.groupby("workload"):
        sub = sub.sort_values("x")
        plt.plot(sub["x"], sub[metric_col], marker="o", label=workload)

    plt.xlabel(x_label)
    plt.ylabel(y_label)

    label_prefix = title_prefix if title_prefix is not None else x_label
    plt.title(f"{y_label} vs {label_prefix}")

    plt.legend()
    plt.grid(True)

    os.makedirs(outdir, exist_ok=True)
    safe_metric = metric_col.replace("/", "_per_").replace(" ", "_")
    fname = f"{safe_metric}_vs_{param_col}.png"

    plt.tight_layout()
    out_path = os.path.join(outdir, fname)
    plt.savefig(out_path)
    plt.close()

    print(f"[saved] {out_path}")


def main():
    df = build_dataframe(SUMMARY_CSV)

    # tsu enq/deq sanity check (참고용)
    if "tsu_User_Transactions_Dequeued" in df.columns:
        diff = df["tsu_User_Transactions_Enqueued"] - df["tsu_User_Transactions_Dequeued"]
        print("[info] tsu enq-deq diff summary:")
        print(diff.describe())

    metrics = [
        "host_BW_MiB_per_s",
        "host_IOPS",
        "host_E2E_Latency_ms_assuming_us",
        "tsu_User_Transactions_Enqueued",
        "ftl_Total_Flash_Read_CMD",
        "ftl_Total_Flash_Program_CMD",
        "ftl_Total_Flash_Erase_CMD",
        "ftl_CMT_Hit_Rate",
        "ftl_Total_GC_Executions",
        "chip_Avg_Fraction_Idle",
        "chip_Avg_Fraction_DataXfer",
        "chip_Avg_Fraction_Exec",
        "energy_Energy_per_IO_Index",
    ]

    # 1) DRAM cache axis
    cache_dir = os.path.join(OUTPUT_ROOT, "cache")
    for metric in metrics:
        plot_metric_vs_param(
            df,
            param_col="cache_size_MiB",
            metric_col=metric,
            outdir=cache_dir,
            title_prefix="DRAM cache size",
        )

    # 2) NVMe queue depth axis
    ioqd_dir = os.path.join(OUTPUT_ROOT, "io_queue_depth")
    for metric in metrics:
        plot_metric_vs_param(
            df,
            param_col="io_queue_depth",
            metric_col=metric,
            outdir=ioqd_dir,
            title_prefix="I/O queue depth",
        )

    # 3) Flash parallelism – channels axis
    ch_dir = os.path.join(OUTPUT_ROOT, "channels")
    for metric in metrics:
        plot_metric_vs_param(
            df,
            param_col="channels",
            metric_col=metric,
            outdir=ch_dir,
            title_prefix="Flash channels",
        )

    # 4) Flash parallelism – ways (chips per channel) axis
    ways_dir = os.path.join(OUTPUT_ROOT, "ways")
    for metric in metrics:
        plot_metric_vs_param(
            df,
            param_col="chips_per_channel",
            metric_col=metric,
            outdir=ways_dir,
            title_prefix="Flash ways (chips per channel)",
        )


if __name__ == "__main__":
    main()

