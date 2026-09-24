import { BUCKET_COLORS, DENSITY_BUCKETS, densityBucket, riskColor, viridisRgb } from "../src/lib/colors";
import { fmtTime } from "../src/lib/format";

describe("colour mapping", () => {
  it("maps risk states to the fixed palette", () => {
    expect(riskColor("LOW")).toBe("#22C55E");
    expect(riskColor("MEDIUM")).toBe("#EAB308");
    expect(riskColor("HIGH")).toBe("#F97316");
    expect(riskColor("CRITICAL")).toBe("#EF4444");
    expect(riskColor("??")).toBe("#8B98A5");
  });

  it("viridis endpoints and clamping", () => {
    expect(viridisRgb(0)).toEqual([68, 1, 84]);
    expect(viridisRgb(1)).toEqual([253, 231, 37]);
    expect(viridisRgb(-5)).toEqual([68, 1, 84]);
    expect(viridisRgb(Number.NaN)).toEqual([68, 1, 84]);
  });

  it("density buckets are within range and monotone", () => {
    let prev = -1;
    for (let d = 0; d <= 10; d += 0.25) {
      const b = densityBucket(d);
      expect(b).toBeGreaterThanOrEqual(0);
      expect(b).toBeLessThan(DENSITY_BUCKETS);
      expect(b).toBeGreaterThanOrEqual(prev);
      prev = b;
    }
    expect(BUCKET_COLORS).toHaveLength(DENSITY_BUCKETS);
  });

  it("formats times", () => {
    expect(fmtTime(0)).toBe("0:00");
    expect(fmtTime(75.9)).toBe("1:15");
    expect(fmtTime(3725)).toBe("1:02:05");
    expect(fmtTime(null)).toBe("--:--");
  });
});
