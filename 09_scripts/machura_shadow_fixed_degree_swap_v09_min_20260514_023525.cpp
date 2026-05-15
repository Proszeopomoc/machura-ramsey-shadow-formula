#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

struct Graph {
    int n = 0;
    vector<vector<unsigned char>> a;
};

struct Hyper {
    int n = 0;
    vector<uint64_t> red;
    vector<uint64_t> blue;
    vector<vector<int>> redInc;
    vector<vector<int>> blueInc;
};

struct State {
    vector<unsigned char> x;
    vector<int> rc;
    vector<int> bc;
    int deg = 0;
    int redPhi = 0;
    int bluePhi = 0;
    int phi = 0;
    long long energy = 0;
};

struct Params {
    int degree = 21;
    int restarts = 100;
    int steps = 500;
    int seed = 450055;
    int target = 2;
    int tabu = 11;
    int shakeAfter = 120;
    long long wPhi = 1000000000LL;
    long long wNear1 = 1000000LL;
    long long wNear2 = 1000LL;
};

struct Delta {
    long long de = 0;
    int dr = 0;
    int db = 0;
    int dp = 0;
};

struct Best {
    int phi = 1000000000;
    int redPhi = 0;
    int bluePhi = 0;
    int deg = 0;
    int restart = -1;
    int step = -1;
    long long totalSteps = 0;
    long long energy = 0;
    string chi;
    string status = "SEARCH_DONE";
};

static string trim(const string& s) {
    size_t p = s.find_first_not_of(" \t\r\n");
    if (p == string::npos) return "";
    size_t q = s.find_last_not_of(" \t\r\n");
    return s.substr(p, q - p + 1);
}

static Graph decode_graph6(string s) {
    s = trim(s);
    string pref = ">>graph6<<";
    if (s.rfind(pref, 0) == 0) s = s.substr(pref.size());

    vector<int> v;
    for (char c : s) v.push_back((int)c - 63);
    if (v.empty()) throw runtime_error("empty graph6");

    int n = 0;
    int pos = 1;

    if (v[0] <= 62) {
        n = v[0];
    } else if (v[0] == 63) {
        if ((int)v.size() < 4) throw runtime_error("bad graph6 n");
        n = (v[1] << 12) | (v[2] << 6) | v[3];
        pos = 4;
    } else {
        throw runtime_error("unsupported graph6 n");
    }

    if (n > 62) throw runtime_error("n > 62 unsupported");

    int need = n * (n - 1) / 2;
    vector<int> bits;
    bits.reserve(v.size() * 6);

    for (int i = pos; i < (int)v.size(); i++) {
        for (int k = 5; k >= 0; k--) bits.push_back((v[i] >> k) & 1);
    }

    if ((int)bits.size() < need) throw runtime_error("graph6 data too short");

    Graph g;
    g.n = n;
    g.a.assign(n, vector<unsigned char>(n, 0));

    int p = 0;
    for (int j = 1; j < n; j++) {
        for (int i = 0; i < j; i++) {
            unsigned char e = (unsigned char)bits[p++];
            g.a[i][j] = e;
            g.a[j][i] = e;
        }
    }

    return g;
}

static uint64_t mask4(int i, int j, int k, int l) {
    return (1ULL << i) | (1ULL << j) | (1ULL << k) | (1ULL << l);
}

static bool red4(const Graph& g, int i, int j, int k, int l) {
    return g.a[i][j] && g.a[i][k] && g.a[i][l] && g.a[j][k] && g.a[j][l] && g.a[k][l];
}

static bool blue4(const Graph& g, int i, int j, int k, int l) {
    return !g.a[i][j] && !g.a[i][k] && !g.a[i][l] && !g.a[j][k] && !g.a[j][l] && !g.a[k][l];
}

static Hyper build_hyper(const Graph& g) {
    Hyper h;
    h.n = g.n;
    h.redInc.assign(g.n, {});
    h.blueInc.assign(g.n, {});

    for (int i = 0; i < g.n; i++) {
        for (int j = i + 1; j < g.n; j++) {
            for (int k = j + 1; k < g.n; k++) {
                for (int l = k + 1; l < g.n; l++) {
                    uint64_t m = mask4(i, j, k, l);
                    if (red4(g, i, j, k, l)) h.red.push_back(m);
                    if (blue4(g, i, j, k, l)) h.blue.push_back(m);
                }
            }
        }
    }

    for (int e = 0; e < (int)h.red.size(); e++) {
        uint64_t m = h.red[e];
        for (int v = 0; v < h.n; v++) if ((m >> v) & 1ULL) h.redInc[v].push_back(e);
    }

    for (int e = 0; e < (int)h.blue.size(); e++) {
        uint64_t m = h.blue[e];
        for (int v = 0; v < h.n; v++) if ((m >> v) & 1ULL) h.blueInc[v].push_back(e);
    }

    return h;
}

static long long pressure(int c, const Params& p) {
    if (c >= 4) return p.wPhi;
    if (c == 3) return p.wNear1;
    if (c == 2) return p.wNear2;
    return 0;
}

static long long compute_energy(const Hyper& h, const State& s, const Params& p) {
    long long e = 0;
    for (int c : s.rc) e += pressure(c, p);
    for (int c : s.bc) e += pressure(c, p);
    return e;
}

static State init_state(const Hyper& h, const Params& p, mt19937_64& rng) {
    State s;
    s.x.assign(h.n, 0);
    s.rc.assign(h.red.size(), 0);
    s.bc.assign(h.blue.size(), 0);

    vector<int> perm(h.n);
    iota(perm.begin(), perm.end(), 0);
    shuffle(perm.begin(), perm.end(), rng);

    int d = p.degree;
    if (d < 0) d = h.n / 2;
    if (d > h.n) d = h.n;

    for (int i = 0; i < d; i++) s.x[perm[i]] = 1;
    s.deg = d;

    for (int e = 0; e < (int)h.red.size(); e++) {
        uint64_t m = h.red[e];
        int c = 0;
        for (int v = 0; v < h.n; v++) if (((m >> v) & 1ULL) && s.x[v]) c++;
        s.rc[e] = c;
        if (c == 4) s.redPhi++;
    }

    for (int e = 0; e < (int)h.blue.size(); e++) {
        uint64_t m = h.blue[e];
        int c = 0;
        for (int v = 0; v < h.n; v++) if (((m >> v) & 1ULL) && !s.x[v]) c++;
        s.bc[e] = c;
        if (c == 4) s.bluePhi++;
    }

    s.phi = s.redPhi + s.bluePhi;
    s.energy = compute_energy(h, s, p);
    return s;
}

static void add_touched(const vector<int>& inc, vector<int>& mark, int stamp, vector<int>& touched) {
    for (int e : inc) {
        if (mark[e] != stamp) {
            mark[e] = stamp;
            touched.push_back(e);
        }
    }
}

static Delta swap_delta(
    const Hyper& h,
    const State& s,
    int one,
    int zero,
    const Params& p,
    vector<int>& rm,
    vector<int>& bm,
    int& rs,
    int& bs
) {
    Delta d;

    vector<int> touched;
    rs++;
    add_touched(h.redInc[one], rm, rs, touched);
    add_touched(h.redInc[zero], rm, rs, touched);

    for (int e : touched) {
        uint64_t m = h.red[e];
        int hasOne = ((m >> one) & 1ULL) ? 1 : 0;
        int hasZero = ((m >> zero) & 1ULL) ? 1 : 0;
        int before = s.rc[e];
        int after = before - hasOne + hasZero;

        d.de += pressure(after, p) - pressure(before, p);
        d.dr += (after == 4 ? 1 : 0) - (before == 4 ? 1 : 0);
    }

    touched.clear();
    bs++;
    add_touched(h.blueInc[one], bm, bs, touched);
    add_touched(h.blueInc[zero], bm, bs, touched);

    for (int e : touched) {
        uint64_t m = h.blue[e];
        int hasOne = ((m >> one) & 1ULL) ? 1 : 0;
        int hasZero = ((m >> zero) & 1ULL) ? 1 : 0;
        int before = s.bc[e];
        int after = before + hasOne - hasZero;

        d.de += pressure(after, p) - pressure(before, p);
        d.db += (after == 4 ? 1 : 0) - (before == 4 ? 1 : 0);
    }

    d.dp = d.dr + d.db;
    return d;
}

static void apply_swap(const Hyper& h, State& s, int one, int zero, const Delta& d) {
    for (int e : h.redInc[one]) s.rc[e]--;
    for (int e : h.redInc[zero]) s.rc[e]++;

    for (int e : h.blueInc[one]) s.bc[e]++;
    for (int e : h.blueInc[zero]) s.bc[e]--;

    s.x[one] = 0;
    s.x[zero] = 1;

    s.redPhi += d.dr;
    s.bluePhi += d.db;
    s.phi += d.dp;
    s.energy += d.de;
}

static void ones_zeros(const State& s, vector<int>& ones, vector<int>& zeros) {
    ones.clear();
    zeros.clear();
    for (int i = 0; i < (int)s.x.size(); i++) {
        if (s.x[i]) ones.push_back(i);
        else zeros.push_back(i);
    }
}

static string chi_string(const State& s) {
    string out;
    for (unsigned char c : s.x) out.push_back(c ? '1' : '0');
    return out;
}

static Best search_one(const Hyper& h, const Params& p, int seed) {
    mt19937_64 rng((uint64_t)seed);
    Best best;

    vector<int> rm(h.red.size(), 0), bm(h.blue.size(), 0);
    int rs = 0, bs = 0;

    for (int r = 0; r < p.restarts; r++) {
        State s = init_state(h, p, rng);
        vector<int> tabu(h.n, -1000000000);
        vector<int> ones, zeros;
        int noImprove = 0;

        for (int step = 0; step < p.steps; step++) {
            best.totalSteps++;

            if (s.phi < best.phi) {
                best.phi = s.phi;
                best.redPhi = s.redPhi;
                best.bluePhi = s.bluePhi;
                best.deg = s.deg;
                best.restart = r;
                best.step = step;
                best.energy = s.energy;
                best.chi = chi_string(s);
                noImprove = 0;
            } else {
                noImprove++;
            }

            if (s.phi <= p.target) {
                best.status = "FOUND_TARGET";
                return best;
            }

            ones_zeros(s, ones, zeros);

            long long bestDE = 9223372036854775807LL;
            vector<pair<int,int>> cand;
            vector<Delta> candD;

            for (int i : ones) {
                for (int j : zeros) {
                    Delta d = swap_delta(h, s, i, j, p, rm, bm, rs, bs);

                    bool isTabu = (step < tabu[i]) || (step < tabu[j]);
                    bool aspiration = s.phi + d.dp < best.phi;
                    if (isTabu && !aspiration) continue;

                    if (d.de < bestDE) {
                        bestDE = d.de;
                        cand.clear();
                        candD.clear();
                        cand.push_back({i, j});
                        candD.push_back(d);
                    } else if (d.de == bestDE) {
                        cand.push_back({i, j});
                        candD.push_back(d);
                    }
                }
            }

            if (cand.empty()) {
                for (int i : ones) {
                    for (int j : zeros) {
                        Delta d = swap_delta(h, s, i, j, p, rm, bm, rs, bs);
                        if (d.de < bestDE) {
                            bestDE = d.de;
                            cand.clear();
                            candD.clear();
                            cand.push_back({i, j});
                            candD.push_back(d);
                        } else if (d.de == bestDE) {
                            cand.push_back({i, j});
                            candD.push_back(d);
                        }
                    }
                }
            }

            if (cand.empty()) break;

            bool shake = (noImprove >= p.shakeAfter && bestDE >= 0);

            if (shake) {
                int swaps = 2 + (int)(rng() % 6);
                for (int z = 0; z < swaps; z++) {
                    ones_zeros(s, ones, zeros);
                    if (ones.empty() || zeros.empty()) break;

                    int i = ones[(int)(rng() % ones.size())];
                    int j = zeros[(int)(rng() % zeros.size())];
                    Delta d = swap_delta(h, s, i, j, p, rm, bm, rs, bs);
                    apply_swap(h, s, i, j, d);

                    tabu[i] = step + p.tabu + (int)(rng() % 5);
                    tabu[j] = step + p.tabu + (int)(rng() % 5);
                }
                noImprove = 0;
            } else {
                int pick = (int)(rng() % cand.size());
                int i = cand[pick].first;
                int j = cand[pick].second;
                Delta d = candD[pick];

                apply_swap(h, s, i, j, d);

                tabu[i] = step + p.tabu + (int)(rng() % 5);
                tabu[j] = step + p.tabu + (int)(rng() % 5);
            }
        }
    }

    return best;
}

static vector<pair<int,string>> read_tokens(const string& path, int limit) {
    ifstream in(path);
    if (!in) throw runtime_error("cannot open input");

    vector<pair<int,string>> out;
    string line;
    int lineno = 0;

    while (getline(in, line)) {
        lineno++;
        line = trim(line);
        if (line.empty() || line[0] == '#') continue;

        string tok;
        stringstream ss(line);
        ss >> tok;
        out.push_back({lineno, tok});

        if (limit > 0 && (int)out.size() >= limit) break;
    }

    return out;
}

static string arg(int argc, char** argv, const string& name, const string& def) {
    for (int i = 1; i + 1 < argc; i++) if (string(argv[i]) == name) return argv[i + 1];
    return def;
}

static int argi(int argc, char** argv, const string& name, int def) {
    return stoi(arg(argc, argv, name, to_string(def)));
}

static long long argll(int argc, char** argv, const string& name, long long def) {
    return stoll(arg(argc, argv, name, to_string(def)));
}

int main(int argc, char** argv) {
    try {
        string input = arg(argc, argv, "--input", "");
        string outdir = arg(argc, argv, "--outdir", "");

        if (input.empty() || outdir.empty()) {
            cerr << "Missing --input or --outdir\n";
            return 2;
        }

        Params p;
        p.degree = argi(argc, argv, "--degree", 21);
        p.restarts = argi(argc, argv, "--restarts", 100);
        p.steps = argi(argc, argv, "--steps", 500);
        p.seed = argi(argc, argv, "--seed", 450055);
        p.target = argi(argc, argv, "--target", 2);
        p.tabu = argi(argc, argv, "--tabu", 11);
        p.shakeAfter = argi(argc, argv, "--shake-after", 120);
        p.wPhi = argll(argc, argv, "--w-phi", 1000000000LL);
        p.wNear1 = argll(argc, argv, "--w-near1", 1000000LL);
        p.wNear2 = argll(argc, argv, "--w-near2", 1000LL);

        int limit = argi(argc, argv, "--limit", 0);

        vector<pair<int,string>> tokens = read_tokens(input, limit);

        string resultsPath = outdir + "\\RESULTS_SHADOW_FIXED_DEGREE_SWAP_V09_MIN.tsv";
        string summaryPath = outdir + "\\SUMMARY_SHADOW_FIXED_DEGREE_SWAP_V09_MIN.txt";

        ofstream res(resultsPath);
        if (!res) throw runtime_error("cannot write results");

        res << "record_index\tline_number\tn\tred_pred\tblue_pred\tstatus\tbest_phi\tred_phi\tblue_phi\tdegree\trestart\tstep\ttotal_steps\tenergy\tchi\n";

        int idx = 0;
        int found = 0;
        int globalBest = 1000000000;

        auto t0 = chrono::steady_clock::now();

        for (auto& item : tokens) {
            idx++;

            Graph g = decode_graph6(item.second);
            Hyper h = build_hyper(g);

            Best b = search_one(h, p, p.seed + idx * 1009);

            if (b.status == "FOUND_TARGET") found++;
            globalBest = min(globalBest, b.phi);

            res << idx << "\t"
                << item.first << "\t"
                << g.n << "\t"
                << h.red.size() << "\t"
                << h.blue.size() << "\t"
                << b.status << "\t"
                << b.phi << "\t"
                << b.redPhi << "\t"
                << b.bluePhi << "\t"
                << b.deg << "\t"
                << b.restart << "\t"
                << b.step << "\t"
                << b.totalSteps << "\t"
                << b.energy << "\t"
                << b.chi << "\n";

            cout << "REC " << idx
                 << " line=" << item.first
                 << " n=" << g.n
                 << " redPred=" << h.red.size()
                 << " bluePred=" << h.blue.size()
                 << " bestPhi=" << b.phi
                 << " red=" << b.redPhi
                 << " blue=" << b.bluePhi
                 << " deg=" << b.deg
                 << " status=" << b.status
                 << " steps=" << b.totalSteps
                 << "\n";
        }

        auto t1 = chrono::steady_clock::now();
        double sec = chrono::duration<double>(t1 - t0).count();

        ofstream sum(summaryPath);
        sum << "MACHURA SHADOW FIXED-DEGREE SWAP HEURISTIC V09 MIN\n";
        sum << "==================================================\n\n";
        sum << "INPUT: " << input << "\n";
        sum << "RECORDS: " << tokens.size() << "\n";
        sum << "DEGREE: " << p.degree << "\n";
        sum << "RESTARTS: " << p.restarts << "\n";
        sum << "STEPS: " << p.steps << "\n";
        sum << "TARGET: " << p.target << "\n";
        sum << "TABU: " << p.tabu << "\n";
        sum << "SHAKE_AFTER: " << p.shakeAfter << "\n";
        sum << "W_PHI: " << p.wPhi << "\n";
        sum << "W_NEAR1: " << p.wNear1 << "\n";
        sum << "W_NEAR2: " << p.wNear2 << "\n";
        sum << "FOUND_TARGET_RECORDS: " << found << "\n";
        sum << "GLOBAL_BEST_PHI: " << globalBest << "\n";
        sum << "ELAPSED_SEC: " << sec << "\n\n";
        sum << "METHOD:\n";
        sum << "Fixed-degree swap search on chi.\n";
        sum << "Each move swaps one 1-bit and one 0-bit, preserving degree exactly.\n";
        sum << "Objective uses completed shadow plus near-shadow pressure.\n";

        cout << "DONE\n";
        cout << "RESULTS: " << resultsPath << "\n";
        cout << "SUMMARY: " << summaryPath << "\n";
        cout << "ELAPSED_SEC: " << sec << "\n";
        cout << "FOUND_TARGET_RECORDS: " << found << "\n";
        cout << "GLOBAL_BEST_PHI: " << globalBest << "\n";

        return 0;
    } catch (const exception& e) {
        cerr << "ERROR: " << e.what() << "\n";
        return 1;
    }
}
