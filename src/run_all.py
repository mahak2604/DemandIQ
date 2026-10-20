"""Run the whole DemandIQ pipeline, step by step (about 8-10 minutes on a laptop)."""
import time

import draw_architecture
import step1_prepare_data
import step2_store_segments
import step3_demand_model
import step4_stockout_model
import step5_reorder_policies
import step6_explain

if __name__ == "__main__":
    start = time.time()
    for step in (draw_architecture, step1_prepare_data, step2_store_segments, step3_demand_model,
                 step4_stockout_model, step5_reorder_policies, step6_explain):
        t = time.time()
        step.main()
        print(f"  -> done in {time.time() - t:.0f}s\n")
    print(f"Pipeline finished in {(time.time() - start) / 60:.1f} minutes.")
