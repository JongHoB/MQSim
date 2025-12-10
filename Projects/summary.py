import pandas as pd

df = pd.read_csv("mqsim_summary.csv")

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


def cache_str_to_mib(s: str) -> float:
    if not isinstance(s, str):
        return float("nan")
    s = s.strip()
    if s.endswith("MB"):
        return float(s[:-2])
    if s.endswith("GB"):
        return float(s[:-2]) * 1024
    return float("nan")


rows = []

# ---------- synthetic: cache 축 (DRAM buffer size) ----------
syn_cache = df[df["category"] == "cache"].copy()
syn_cache["axis"] = "DRAM_Cache"
syn_cache["axis_param"] = "cache_size"
syn_cache["axis_value"] = syn_cache["cache_size"]
syn_cache["axis_value_sort"] = syn_cache["cache_size"].map(cache_str_to_mib)
syn_cache["workload"] = syn_cache.apply(
    lambda r: f"{r['access_pattern']}_{r['block_size']}", axis=1
)
rows.append(syn_cache)

# ---------- synthetic: NVMe queueing (IOQD) ----------
syn_ioqd = df[df["category"] == "ioqd"].copy()
syn_ioqd["axis"] = "NVMe_Queueing"
syn_ioqd["axis_param"] = "io_queue_depth"
syn_ioqd["axis_value"] = syn_ioqd["io_queue_depth"]
syn_ioqd["axis_value_sort"] = syn_ioqd["io_queue_depth"]
syn_ioqd["workload"] = syn_ioqd.apply(
    lambda r: f"{r['access_pattern']}_{r['block_size']}", axis=1
)
rows.append(syn_ioqd)

# ---------- synthetic: Flash parallelism (channels / ways 분리) ----------
syn_ch = df[df["category"] == "ch_chip"].copy()

# 채널 축: chips_per_channel == 4인 것만
syn_ch_channels = syn_ch[syn_ch["chips_per_channel"] == 4].copy()
syn_ch_channels["axis"] = "Flash_Channels"
syn_ch_channels["axis_param"] = "channels"
syn_ch_channels["axis_value"] = syn_ch_channels["channels"]
syn_ch_channels["axis_value_sort"] = syn_ch_channels["channels"]
syn_ch_channels["workload"] = syn_ch_channels.apply(
    lambda r: f"{r['access_pattern']}_{r['block_size']}", axis=1
)
rows.append(syn_ch_channels)

# ways 축: channels == 8인 것만
syn_ch_ways = syn_ch[syn_ch["channels"] == 8].copy()
syn_ch_ways["axis"] = "Flash_Ways"
syn_ch_ways["axis_param"] = "chips_per_channel"
syn_ch_ways["axis_value"] = syn_ch_ways["chips_per_channel"]
syn_ch_ways["axis_value_sort"] = syn_ch_ways["chips_per_channel"]
syn_ch_ways["workload"] = syn_ch_ways.apply(
    lambda r: f"{r['access_pattern']}_{r['block_size']}", axis=1
)
rows.append(syn_ch_ways)

# ---------- TPCC: cache / ioqd / ch_chip 각각 동일 축으로 매핑 ----------
tpcc = df[df["category"] == "tpcc"].copy()

# TPCC - cache 축
tpcc_cache = tpcc[tpcc["tpcc_variant"] == "cache"].copy()
tpcc_cache["axis"] = "DRAM_Cache"
tpcc_cache["axis_param"] = "cache_size"
tpcc_cache["axis_value"] = tpcc_cache["cache_size"]
tpcc_cache["axis_value_sort"] = tpcc_cache["cache_size"].map(cache_str_to_mib)
tpcc_cache["workload"] = "tpcc"
rows.append(tpcc_cache)

# TPCC - IOQD 축
tpcc_ioqd = tpcc[tpcc["tpcc_variant"] == "ioqd"].copy()
tpcc_ioqd["axis"] = "NVMe_Queueing"
tpcc_ioqd["axis_param"] = "io_queue_depth"
tpcc_ioqd["axis_value"] = tpcc_ioqd["io_queue_depth"]
tpcc_ioqd["axis_value_sort"] = tpcc_ioqd["io_queue_depth"]
tpcc_ioqd["workload"] = "tpcc"
rows.append(tpcc_ioqd)

# TPCC - ch_chip → channels / ways로 분할
tpcc_ch = tpcc[tpcc["tpcc_variant"] == "ch_chip"].copy()

tpcc_ch_channels = tpcc_ch[tpcc_ch["chips_per_channel"] == 4].copy()
tpcc_ch_channels["axis"] = "Flash_Channels"
tpcc_ch_channels["axis_param"] = "channels"
tpcc_ch_channels["axis_value"] = tpcc_ch_channels["channels"]
tpcc_ch_channels["axis_value_sort"] = tpcc_ch_channels["channels"]
tpcc_ch_channels["workload"] = "tpcc"
rows.append(tpcc_ch_channels)

tpcc_ch_ways = tpcc_ch[tpcc_ch["channels"] == 8].copy()
tpcc_ch_ways["axis"] = "Flash_Ways"
tpcc_ch_ways["axis_param"] = "chips_per_channel"
tpcc_ch_ways["axis_value"] = tpcc_ch_ways["chips_per_channel"]
tpcc_ch_ways["axis_value_sort"] = tpcc_ch_ways["chips_per_channel"]
tpcc_ch_ways["workload"] = "tpcc"
rows.append(tpcc_ch_ways)

axis_df = pd.concat(rows, ignore_index=True)

# 참고: enq vs deq 차이 확인하고 싶으면 이렇게 한 번 보면 됨
axis_df["tsu_diff_enq_deq"] = (
    axis_df["tsu_User_Transactions_Enqueued"]
    - axis_df["tsu_User_Transactions_Dequeued"]
)

# 축/값/워크로드별 평균 metric 테이블
agg = (
    axis_df
    .groupby(["axis", "axis_value", "axis_value_sort", "workload"])[metrics]
    .mean()
    .reset_index()
)

agg.to_csv("mqsim_axis_metrics.csv", index=False)

