// The gala night behind the art: a deep night, three searchlights sweeping up from below, the red carpet
  // running down to us between gold ropes, gold stars twinkling, a warm glory behind the art, a photographer's
  // flash now and then.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec3 col = mix(vec3(0.03, 0.02, 0.06), vec3(0.14, 0.08, 0.04), smoothstep(0.5, -0.4, c.y));
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    vec2 src = vec2((fk - 1.0) * 0.3, -0.55);
    float ang = 1.5708 + 0.45 * sin(t * (0.5 + 0.13 * fk) + fk * 2.0);
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 q = c - src;
    float along = dot(q, dir);
    col += vec3(1.0, 0.86, 0.55) * smoothstep(0.015 + along * 0.08, 0.0, abs(dot(q, vec2(-dir.y, dir.x)))) * step(0.0, along) * 0.35;
  }
  col += vec3(1.0, 0.8, 0.4) * exp(-length((c - vec2(0.0, 0.08)) * vec2(1.0, 0.8)) * 3.5) * 0.55;
  float glory = pow(0.5 + 0.5 * sin(atan(c.y - 0.08, c.x) * 14.0 + t * 0.3), 5.0) * smoothstep(0.6, 0.1, length(c - vec2(0.0, 0.08)));
  col += vec3(1.0, 0.85, 0.5) * glory * 0.25;
  float yc = c.y + 0.22;
  float z = 0.06 / max(-yc, 0.0005);
  float onCarpet = step(yc, 0.0) * smoothstep(0.125, 0.115, abs(c.x * z));
  vec3 velvet = vec3(0.6, 0.04, 0.08) * (0.65 + 0.35 * fbm(vec2(c.x * z * 40.0, z * 5.0))) * (0.5 + 0.5 * smoothstep(2.5, 0.3, z));
  col = mix(col, velvet, onCarpet);
  col += vec3(1.0, 0.75, 0.35) * smoothstep(0.01, 0.0, abs(abs(c.x * z) - 0.125)) * step(yc, 0.0) * 0.8;
  vec2 sg = c * 34.0;
  vec2 cell = floor(sg);
  float star = step(0.86, hash(cell)) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 3.0 + hash(cell + 3.0) * 20.0));
  col += vec3(1.0, 0.85, 0.45) * star * step(-0.15, c.y);
  float ph = fract(t / 2.3);
  vec2 fl = c - vec2(hash(vec2(floor(t / 2.3), 1.0)) - 0.5, hash(vec2(floor(t / 2.3), 2.0)) * 0.4 - 0.3) * vec2(0.6, 1.0);
  col += vec3(1.0) * exp(-length(fl) * 40.0) * exp(-ph * 30.0) * 1.5;
  o = vec4(col, 1.0);
