// Chronique — the booster stage: a hall of marble columns at golden hour, sunbeams slanting between them, dust
  // drifting in the light, crimson banners stirring (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.42, 0.28, 0.16), vec3(0.95, 0.72, 0.42), smoothstep(-0.5, 0.45, c.y)), 1.0);
  // sunbeams slanting from the upper left
  float sb = c.x * 0.8 + c.y * 0.6;
  float rays = pow(0.5 + 0.5 * sin(sb * 14.0 + 0.6 * sin(t * 0.4)), 6.0);
  o = over(o, vec3(1.0, 0.86, 0.55), rays * 0.35 * smoothstep(-0.6, 0.4, c.y));
  // the columns: fluted shafts, their capitals and bases
  float cx = fract(c.x * 1.6 + 0.5) - 0.5;
  float shaft = step(abs(cx), 0.11);
  float flute = 0.85 + 0.15 * cos(cx * 120.0);
  float lit = 0.75 + 0.25 * smoothstep(-0.11, 0.11, cx);
  vec3 marble = vec3(0.92, 0.88, 0.8) * flute * lit;
  float cap = step(abs(cx), 0.16) * (step(0.36, c.y) * step(c.y, 0.41) + step(-0.45, c.y) * step(c.y, -0.4));
  o = over(o, marble, shaft * step(-0.4, c.y) * step(c.y, 0.36));
  o = over(o, vec3(0.86, 0.8, 0.7), cap);
  // the architrave across the top, the floor's shadow
  o = over(o, vec3(0.84, 0.78, 0.66), step(0.41, c.y) * step(c.y, 0.5));
  o = over(o, vec3(0.3, 0.2, 0.12), smoothstep(-0.4, -0.55, c.y) * 0.8);
  // crimson banners between the columns, stirring
  float bx = fract(c.x * 1.6) - 0.5;
  float wave = 0.012 * sin(c.y * 9.0 - t * 1.4);
  float ax2 = abs(bx + wave);
  float tail = -0.2 + 0.06 * (1.0 - ax2 / 0.07);   // a swallowtail end
  float ban = step(ax2, 0.07) * step(tail, c.y) * step(c.y, 0.41);
  o = over(o, vec3(0.6, 0.1, 0.12) * (0.8 + 0.2 * sin(c.y * 30.0 - t)), ban * 0.95);
  o = over(o, vec3(0.95, 0.78, 0.35), step(abs(ax2 - 0.065), 0.006) * step(tail, c.y) * step(c.y, 0.41));
  o = over(o, vec3(0.95, 0.78, 0.35), step(ax2, 0.07) * step(abs(c.y - 0.3), 0.008));
  // dust in the light
  vec2 g = c * 22.0 + vec2(t * 0.3, -t * 0.15);
  float dust = step(0.985, hash(floor(g))) * smoothstep(0.35, 0.0, length(fract(g) - 0.5));
  o = over(o, vec3(1.0, 0.92, 0.7), dust * (0.4 + rays));
  o.rgb *= smoothstep(1.35, 0.35, length(c * vec2(0.8, 1.0)));
