"""
Generate dissertation-ready benchmark graphs from benchmark_summary.csv.
"""

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

RESULTS_DIR = Path("benchmark/results")
SUMMARY = RESULTS_DIR / "benchmark_summary.csv"

df = pd.read_csv(SUMMARY)

def save_line(metric: str, ylabel: str, filename: str):
    plt.figure(figsize=(9, 5))
    for architecture in df["architecture"].unique():
        sub = df[df["architecture"] == architecture]
        plt.plot(sub["request_load"], sub[metric], marker="o", label=architecture)
    plt.xlabel("Request Load")
    plt.ylabel(ylabel)
    plt.title(ylabel + " Comparison")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / filename, dpi=300)
    plt.close()

save_line("avg_latency_ms", "Average Latency (ms)", "latency_comparison.png")
save_line("p95_latency_ms", "P95 Latency (ms)", "p95_latency_comparison.png")
save_line("throughput_requests_per_second", "Throughput (requests/second)", "throughput_comparison.png")
save_line("success_rate_percent", "Success Rate (%)", "success_rate_comparison.png")

print("Graphs generated:")
print(RESULTS_DIR / "latency_comparison.png")
print(RESULTS_DIR / "p95_latency_comparison.png")
print(RESULTS_DIR / "throughput_comparison.png")
print(RESULTS_DIR / "success_rate_comparison.png")
