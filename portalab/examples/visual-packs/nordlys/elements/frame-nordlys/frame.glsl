  // Nordlys frame — the shape's frame: p (in half heights), d (distance to its edge, < 0 inside), ax (its
  // width over its height), t (time); writes its colour into o. Drawn round the avatar, never over it.
  float band = smoothstep(0.32, 0.0, abs(d - 0.06));
  float a = atan(p.y, p.x);
  float flow = fbm(vec2(a * 2.2 + t * 0.5, d * 6.0 - t * 0.3));
  vec3 green = vec3(0.2, 1.0, 0.6);
  vec3 violet = vec3(0.6, 0.35, 1.0);
  vec3 col = mix(green, violet, smoothstep(0.35, 0.75, flow + 0.25 * sin(a * 3.0 + t)));
  float glow = band * (0.45 + 0.75 * flow);
  float ice = smoothstep(0.03, 0.0, abs(d)) * 0.9;
  o = over(o, col, glow * step(-0.02, d));
  o = over(o, vec3(0.85, 1.0, 0.98), ice);
  float spark = step(0.97, hash(floor(vec2(a * 18.0, t * 3.0)))) * band;
  o = over(o, vec3(1.0), spark * 0.8);
