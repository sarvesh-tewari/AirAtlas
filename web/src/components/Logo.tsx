// AirAtlas logo, recreated from the brand design as theme-aware markup (crisp at any size, uses
// Inter + the design tokens). "Air" uses --heading (navy in light, near-white in dark); "Atlas"
// carries the AQI-scale gradient in both themes. Size is driven by the root font-size.
export function Logo({
  variant = "wordmark",
  className = "",
  ...rest
}: {
  variant?: "lockup" | "wordmark" | "mark";
  className?: string;
} & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={`logo ${className}`} role="img" aria-label="AirAtlas, air quality & weather data" {...rest}>
      <span className="logo-mark" aria-hidden="true"><span>A</span></span>
      {variant !== "mark" && (
        <span className="logo-text">
          <span className="logo-word" aria-hidden="true">
            Air<span className="logo-atlas">Atlas</span>
          </span>
          {variant === "lockup" && (
            <span className="logo-tagline" aria-hidden="true">Air quality &amp; weather data</span>
          )}
        </span>
      )}
    </span>
  );
}
