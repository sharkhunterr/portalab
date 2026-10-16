// Portalab — badge/holo: the « holo » effect (spec 028, B2)
  float sweep = p.x * 0.35 + p.y * 0.6 + t * 0.5;
  vec3 irid = 0.5 + 0.5 * cos(6.2831 * (sweep + fbm(p * 2.0) * 0.6 + vec3(0.0, 0.33, 0.67)));
  irid = mix(vec3(0.08, 0.06, 0.15), irid, 0.6);
  float lines = 0.85 + 0.15 * sin(gl_FragCoord.y * 1.3 + t * 6.0);
  float band = smoothstep(0.35, 0.0, abs(p.x - p.y * 0.4 - mod(t * 2.0, 2.0 * ax + 4.0) + ax + 2.0));
  vec3 body = irid * lines + vec3(1.0) * band * 0.45;
  body += vec3(0.9, 0.5, 1.0) * smoothstep(-0.15, 0.0, d) * 0.6;
  vec3 neon = mix(vec3(0.0, 1.0, 1.0), vec3(1.0, 0.2, 0.9), 0.5 + 0.5 * sin(t * 2.0 + p.x));
  o = over(o, neon, exp(-max(d, 0.0) * 5.0) * 0.45 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
