// Sumi — the booster stage: black urushi lacquer warming to red-brown at its heart, a slow sheen gliding across
  // it; gold seigaiha waves rising from its foot (maki-e); nashiji gold dust twinkling; gold flecks drifting up;
  // ink mist wandering; a great gold ensō faint behind it all (a stage: gl_FragCoord, u_res, t; into o).
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.03, 0.016, 0.014, 1.0);
  o = over(o, vec3(0.2, 0.055, 0.035), exp(-length(c * vec2(0.75, 1.1)) * 2.4) * 0.7);
  // the lacquer's sheen, a soft band gliding slowly across
  float band = c.x * 0.55 + c.y * 0.85 - 0.45 * sin(t * 0.06);
  o = over(o, vec3(0.55, 0.3, 0.2), exp(-band * band * 22.0) * 0.07);
  // ink mist wandering
  vec2 m = c * 1.6 + vec2(t * 0.012, -t * 0.008);
  float mist = fbm(m + vec2(fbm(m * 1.4 + t * 0.01), fbm(m * 1.2 - 1.7)) * 1.4);
  o = over(o, vec3(0.32, 0.24, 0.22), smoothstep(0.5, 0.85, mist) * 0.09);
  // seigaiha: rows of wave scales rising from the foot, each row over the one behind it, ringed in gold
  vec2 wp = vec2(c.x, -c.y) * 9.0;
  float best = -1.0;
  float ring = 0.0;
  float depth = 0.0;
  for (int dy = 0; dy < 3; dy++) {
    float row = floor(wp.y * 2.0) + float(dy);
    float shift = 0.5 * mod(row, 2.0);
    for (int dx = -1; dx < 2; dx++) {
      vec2 ctr = vec2(floor(wp.x - shift + 0.5) + float(dx) + shift, row * 0.5);
      float dc = length(wp - ctr);
      if (dc < 1.0 && row > best) {
        best = row;
        float k = dc * 4.0;
        ring = smoothstep(0.11, 0.04, abs(k - floor(k + 0.5)));
        depth = dc;
      }
    }
  }
  float foot = smoothstep(-0.05, -0.48, c.y);
  o = over(o, vec3(0.3, 0.09, 0.05), depth * foot * 0.22);
  o = over(o, vec3(0.86, 0.64, 0.24), ring * foot * 0.34);
  // nashiji: gold dust scattered in the lacquer, thicker towards the foot, twinkling
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float size = u_res.y * (0.009 + fk * 0.008);
    vec2 cell = floor(gl_FragCoord.xy / size);
    float h = hash(cell + fk * 17.0);
    vec2 at = (cell + 0.2 + 0.6 * vec2(hash(cell + 3.1), hash(cell + 7.7))) * size;
    float r = length(gl_FragCoord.xy - at) / size;
    float keep = step(0.985 - 0.09 * foot - fk * 0.01, h);
    float twinkle = 0.45 + 0.55 * pow(0.5 + 0.5 * sin(t * (1.0 + 2.0 * h) + h * 40.0), 3.0);
    o = over(o, mix(vec3(0.95, 0.75, 0.32), vec3(1.0, 0.92, 0.65), h), smoothstep(0.16 - fk * 0.04, 0.0, r) * keep * twinkle * 0.8);
  }
  // gold flecks drifting up
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 1.0));
    float h2 = hash(vec2(fk, 2.0));
    float y = fract(h2 - t * (0.012 + 0.02 * h1)) * 1.3 - 0.65;
    vec2 sp = vec2((h1 - 0.5) * asp + 0.04 * sin(t * 0.4 + fk), y);
    float dm = length(c - sp);
    o = over(o, vec3(1.0, 0.85, 0.48), exp(-dm * 420.0) * 0.9 + exp(-dm * 60.0) * 0.12);
  }
  // the great ensō, faint: a brushed circle, heavy where it starts, thinning round towards its end
  float ang = atan(c.y, c.x);
  float u = fract((ang + 2.2) / 6.2831853);
  float rr = length(c * vec2(1.0, 1.04));
  float width = 0.022 * pow(1.0 - u, 0.5) * (1.0 + 0.25 * exp(-u * 30.0));
  float enso = smoothstep(width, width * 0.6, abs(rr - 0.37 - 0.01 * sin(u * 9.0))) * step(u, 0.9);
  float streak = 0.7 + 0.3 * step(0.4, fract((rr - 0.37) * 220.0 + u * 3.0));
  o = over(o, vec3(0.86, 0.64, 0.24), enso * streak * (0.13 + 0.04 * sin(t * 0.5)));
