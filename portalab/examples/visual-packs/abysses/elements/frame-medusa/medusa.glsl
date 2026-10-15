  // Jellyfish frame — p (half heights), d (distance to the shape's edge), t; a glowing rim, tentacles
  // swaying outside it; writes into o, never over the avatar
  float a = atan(p.y, p.x);
  float rim = exp(-abs(d) * 26.0) * (0.75 + 0.25 * sin(t * 2.0));
  float swirl = 0.0;
  for (int j = 0; j < 7; j++) {
    float fj = float(j);
    float ta = fj / 7.0 * 6.2832 + 0.25 * sin(t * 0.8 + fj);
    float off = abs(sin((a - ta) * 0.5));
    swirl += smoothstep(0.08, 0.0, off - 0.02 * sin(d * 18.0 - t * 3.0)) * smoothstep(0.55, 0.05, d) * step(0.0, d);
  }
  vec3 glow = mix(vec3(0.2, 1.0, 0.85), vec3(0.65, 0.45, 1.0), 0.5 + 0.5 * sin(a * 2.0 + t));
  o = over(o, glow, (rim + swirl * 0.55) * step(-0.03, d));
