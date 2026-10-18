// Clock frame — the shape's frame: p, d (< 0 inside), ax, t; writes into o. A brass dial round the avatar,
  // its graduations, a hand ticking forward, a puff of steam now and then.
  float ring = smoothstep(0.22, 0.0, abs(d - 0.08));
  float a = atan(p.y, p.x);
  vec3 brass = mix(vec3(0.62, 0.42, 0.16), vec3(0.95, 0.75, 0.38), 0.5 + 0.5 * sin(a * 2.0 + 0.8));
  o = over(o, brass, ring * step(-0.02, d));
  float ticks = step(0.92, fract(a / 6.2832 * 60.0)) * smoothstep(0.06, 0.02, abs(d - 0.08));
  float hours = step(0.8, fract(a / 6.2832 * 12.0)) * smoothstep(0.1, 0.03, abs(d - 0.08));
  o = over(o, vec3(0.15, 0.08, 0.02), clamp(ticks + hours, 0.0, 1.0));
  float tick = floor(t) / 60.0 * 6.2832;
  float hand = smoothstep(0.08, 0.0, abs(sin(a - 1.5708 + tick)) * 2.0) * step(0.0, cos(a - 1.5708 + tick)) * smoothstep(0.25, 0.05, abs(d - 0.12));
  o = over(o, vec3(0.9, 0.2, 0.1), hand);
  float puff = fbm(p * 3.0 + vec2(0.0, -t * 0.6)) * smoothstep(0.4, 0.1, d) * step(0.0, d) * smoothstep(0.3, 1.2, p.y) * step(0.7, fract(t * 0.15));
  o = over(o, vec3(0.9, 0.88, 0.85), puff * 0.5);
