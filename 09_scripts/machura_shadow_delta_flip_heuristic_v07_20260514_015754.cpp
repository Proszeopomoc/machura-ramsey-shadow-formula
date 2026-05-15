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
#include <cmath>

using namespace std;

struct Graph {
    int n = 0;
    vector<vector<unsigned char>> adj;
};

struct Hyper {
    int n = 0;
    int kRed = 0;
    int kBlue = 0;
    vector<uint64_t> red;
    vector<uint64_t> blue;
    vector<vector<int>> redInc;
    vector<vector<int>> blueInc;
    vector<int> incidence;
};

struct State {
    vector<unsigned char> x;
    vector<int> redCnt;
    vector<int> blueCnt;
    int degree = 0;
    int redPhi = 0;
    int bluePhi = 0;
    int phi = 0;
};

struct MoveDelta {
    int dRed = 0;
    int dBlue = 0;
    int dPhi = 0;
    int dDegree = 0;
    long long dObj = 0;
};

struct BestResult {
    int bestPhi = 1000000000;
    int bestRedPhi = 0;
    int bestBluePhi = 0;
    int bestDegree = 0;
    long long steps = 0;
    int restart = -1;
    string chi;
    string status = "NOT_RUN";
};

static string trim(const string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

static int popcnt64(uint64_t x) {
    int c = 0;
    while (x) {
        x &= (x - 1);
        c++;
    }
    return c;
}

static Graph decodeGraph6(string s) {
    s = trim(s);
    string prefix = ">>graph6<<";
    if (s.rfind(prefix, 0) == 0) s = s.substr(prefix.size());

    vector<int> vals;
    for (char c : s) vals.push_back((int)c - 63);
    if (vals.empty()) throw runtime_error("empty graph6");

    int n = 0;
    int pos = 1;

    if (vals[0] <= 62) {
        n = vals[0];
    } else if (vals[0] == 63) {
        if ((int)vals.size() < 4) throw runtime_error("bad graph6 n");
        n = (vals[1] << 12) | (vals[2] << 6) | vals[3];
        pos = 4;
    } else {
        throw runtime_error("unsupported graph6 n");
    }

    if (n > 62) throw runtime_error("n > 62 not supported in uint64 mask engine");

    int need = n * (n - 1) / 2;
    vector<int> bits;
    bits.reserve(vals.size() * 6);

    for (int i = pos; i < (int)vals.size(); i++) {
        int v = vals[i];
        for (int k = 5; k >= 0; k--) bits.push_back((v >> k) & 1);
    }

    if ((int)bits.size() < need) throw runtime_error("graph6 too short");

    Graph g;
    g.n = n;
    g.adj.assign(n, vector<unsigned char>(n, 0));

    int p = 0;
    for (int j = 1; j < n; j++) {
        for (int i = 0; i < j; i++) {
            unsigned char e = (unsigned char)bits[p++];
            g.adj[i][j] = e;
            g.adj[j][i] = e;
        }
    }

    return g;
}

static bool redClique(const Graph& g, const vector<int>& comb) {
    for (int i = 0; i < (int)comb.size(); i++) {
        for (int j = i + 1; j < (int)comb.size(); j++) {
            if (!g.adj[comb[i]][comb[j]]) return false;
        }
    }
    return true;
}

static bool blueClique(const Graph& g, const vector<int>& comb) {
    for (int i = 0; i < (int)comb.size(); i++) {
        for (int j = i + 1; j < (int)comb.size(); j++) {
            if (g.adj[comb[i]][comb[j]]) return false;
        }
    }
    return true;
}

static uint64_t maskOf(const vector<int>& comb) {
    uint64_t m = 0;
    for (int v : comb) m |= (1ULL << v);
    return m;
}

static void genComb(
    int n,
    int k,
    int start,
    vector<int>& cur,
    const Graph& g,
    bool red,
    vector<uint64_t>& out
) {
    if ((int)cur.size() == k) {
        bool ok = red ? redClique(g, cur) : blueClique(g, cur);
        if (ok) out.push_back(maskOf(cur));
        return;
    }

    int need = k - (int)cur.size();
    for (int v = start; v <= n - need; v++) {
        cur.push_back(v);
        genComb(n, k, v + 1, cur, g, red, out);
        cur.pop_back();
    }
}

static Hyper buildHyper(const Graph& g, int a, int b) {
    Hyper h;
    h.n = g.n;
    h.kRed = a - 1;
    h.kBlue = b - 1;
    h.redInc.assign(g.n, {});
    h.blueInc.assign(g.n, {});
    h.incidence.assign(g.n, 0);

    vector<int> cur;
    genComb(g.n, h.kRed, 0, cur, g, true, h.red);
    cur.clear();
    genComb(g.n, h.kBlue, 0, cur, g, false, h.blue);

    for (int eid = 0; eid < (int)h.red.size(); eid++) {
        uint64_t m = h.red[eid];
        for (int v = 0; v < g.n; v++) {
            if ((m >> v) & 1ULL) {
                h.redInc[v].push_back(eid);
                h.incidence[v]++;
            }
        }
    }

    for (int eid = 0; eid < (int)h.blue.size(); eid++) {
        uint64_t m = h.blue[eid];
        for (int v = 0; v < g.n; v++) {
            if ((m >> v) & 1ULL) {
                h.blueInc[v].push_back(eid);
                h.incidence[v]++;
            }
        }
    }

    return h;
}

static int degreePenalty(int degree, int target) {
    if (target < 0) return 0;
    return abs(degree - target);
}

static State initState(const Hyper& h, mt19937_64& rng, int degreeTarget) {
    State s;
    s.x.assign(h.n, 0);
    s.redCnt.assign(h.red.size(), 0);
    s.blueCnt.assign(h.blue.size(), 0);

    vector<int> perm(h.n);
    iota(perm.begin(), perm.end(), 0);
    shuffle(perm.begin(), perm.end(), rng);

    if (degreeTarget >= 0 && degreeTarget <= h.n) {
        for (int i = 0; i < degreeTarget; i++) s.x[perm[i]] = 1;
    } else {
        for (int i = 0; i < h.n; i++) s.x[i] = (unsigned char)(rng() & 1ULL);
    }

    for (int v = 0; v < h.n; v++) if (s.x[v]) s.degree++;

    for (int eid = 0; eid < (int)h.red.size(); eid++) {
        int c = 0;
        uint64_t m = h.red[eid];
        for (int v = 0; v < h.n; v++) if (((m >> v) & 1ULL) && s.x[v]) c++;
        s.redCnt[eid] = c;
        if (c == h.kRed) s.redPhi++;
    }

    for (int eid = 0; eid < (int)h.blue.size(); eid++) {
        int c = 0;
        uint64_t m = h.blue[eid];
        for (int v = 0; v < h.n; v++) if (((m >> v) & 1ULL) && !s.x[v]) c++;
        s.blueCnt[eid] = c;
        if (c == h.kBlue) s.bluePhi++;
    }

    s.phi = s.redPhi + s.bluePhi;
    return s;
}

static MoveDelta calcDelta(const Hyper& h, const State& s, int v, int degreeTarget, int degreeWeight) {
    MoveDelta d;
    int old = s.x[v] ? 1 : 0;
    d.dDegree = old ? -1 : 1;

    for (int eid : h.redInc[v]) {
        int before = s.redCnt[eid];
        int after = before + (old ? -1 : 1);
        int bComp = (before == h.kRed) ? 1 : 0;
        int aComp = (after == h.kRed) ? 1 : 0;
        d.dRed += aComp - bComp;
    }

    for (int eid : h.blueInc[v]) {
        int before = s.blueCnt[eid];
        int after = before + (old ? 1 : -1);
        int bComp = (before == h.kBlue) ? 1 : 0;
        int aComp = (after == h.kBlue) ? 1 : 0;
        d.dBlue += aComp - bComp;
    }

    d.dPhi = d.dRed + d.dBlue;

    int p0 = degreePenalty(s.degree, degreeTarget);
    int p1 = degreePenalty(s.degree + d.dDegree, degreeTarget);

    d.dObj = (long long)d.dPhi * 1000000LL + (long long)degreeWeight * (p1 - p0);
    return d;
}

static void applyFlip(const Hyper& h, State& s, int v, const MoveDelta& d) {
    int old = s.x[v] ? 1 : 0;

    for (int eid : h.redInc[v]) {
        s.redCnt[eid] += old ? -1 : 1;
    }

    for (int eid : h.blueInc[v]) {
        s.blueCnt[eid] += old ? 1 : -1;
    }

    s.x[v] = old ? 0 : 1;
    s.degree += d.dDegree;
    s.redPhi += d.dRed;
    s.bluePhi += d.dBlue;
    s.phi += d.dPhi;
}

static string chiString(const State& s) {
    string out;
    out.reserve(s.x.size());
    for (unsigned char c : s.x) out.push_back(c ? '1' : '0');
    return out;
}

static BestResult runHeuristic(
    const Hyper& h,
    int restarts,
    int stepsPerRestart,
    int seed,
    int degreeTarget,
    int degreeWeight,
    int target,
    int tabuTenure
) {
    mt19937_64 rng(seed);

    BestResult best;
    best.status = "SEARCH_DONE";

    for (int r = 0; r < restarts; r++) {
        State s = initState(h, rng, degreeTarget);
        vector<int> tabu(h.n, -1000000);

        int noImprove = 0;

        for (int step = 0; step < stepsPerRestart; step++) {
            best.steps++;

            if (s.phi < best.bestPhi) {
                best.bestPhi = s.phi;
                best.bestRedPhi = s.redPhi;
                best.bestBluePhi = s.bluePhi;
                best.bestDegree = s.degree;
                best.restart = r;
                best.chi = chiString(s);
                noImprove = 0;
            } else {
                noImprove++;
            }

            if (s.phi <= target) {
                best.status = "FOUND_TARGET";
                return best;
            }

            long long bestObj = 9000000000000000000LL;
            vector<int> candidates;
            vector<MoveDelta> candDelta;

            for (int v = 0; v < h.n; v++) {
                MoveDelta d = calcDelta(h, s, v, degreeTarget, degreeWeight);
                bool isTabu = step < tabu[v];
                bool aspiration = (s.phi + d.dPhi < best.bestPhi);

                if (isTabu && !aspiration) continue;

                if (d.dObj < bestObj) {
                    bestObj = d.dObj;
                    candidates.clear();
                    candDelta.clear();
                    candidates.push_back(v);
                    candDelta.push_back(d);
                } else if (d.dObj == bestObj) {
                    candidates.push_back(v);
                    candDelta.push_back(d);
                }
            }

            if (candidates.empty()) {
                for (int v = 0; v < h.n; v++) {
                    MoveDelta d = calcDelta(h, s, v, degreeTarget, degreeWeight);
                    if (d.dObj < bestObj) {
                        bestObj = d.dObj;
                        candidates.clear();
                        candDelta.clear();
                        candidates.push_back(v);
                        candDelta.push_back(d);
                    } else if (d.dObj == bestObj) {
                        candidates.push_back(v);
                        candDelta.push_back(d);
                    }
                }
            }

            if (candidates.empty()) break;

            int pick = (int)(rng() % candidates.size());
            int v = candidates[pick];
            MoveDelta d = candDelta[pick];

            if (noImprove > 200 && bestObj >= 0) {
                int flips = 3 + (int)(rng() % 7);
                for (int z = 0; z < flips; z++) {
                    int rv = (int)(rng() % h.n);
                    MoveDelta rd = calcDelta(h, s, rv, degreeTarget, degreeWeight);
                    applyFlip(h, s, rv, rd);
                    tabu[rv] = step + tabuTenure + (int)(rng() % 5);
                }
                noImprove = 0;
            } else {
                applyFlip(h, s, v, d);
                tabu[v] = step + tabuTenure + (int)(rng() % 5);
            }
        }
    }

    return best;
}

static vector<pair<int,string>> readTokens(const string& path, int limit) {
    ifstream in(path);
    if (!in) throw runtime_error("cannot open input");

    vector<pair<int,string>> out;
    string line;
    int lineno = 0;

    while (getline(in, line)) {
        lineno++;
        line = trim(line);
        if (line.empty()) continue;
        if (line[0] == '#') continue;

        string token;
        stringstream ss(line);
        ss >> token;
        out.push_back({lineno, token});

        if (limit > 0 && (int)out.size() >= limit) break;
    }

    return out;
}

static string getArg(int argc, char** argv, const string& name, const string& def) {
    for (int i = 1; i + 1 < argc; i++) {
        if (string(argv[i]) == name) return string(argv[i + 1]);
    }
    return def;
}

static int getArgInt(int argc, char** argv, const string& name, int def) {
    return stoi(getArg(argc, argv, name, to_string(def)));
}

int main(int argc, char** argv) {
    try {
        string input = getArg(argc, argv, "--input", "");
        string outdir = getArg(argc, argv, "--outdir", "");
        int a = getArgInt(argc, argv, "--a", 5);
        int b = getArgInt(argc, argv, "--b", 5);
        int limit = getArgInt(argc, argv, "--limit", 0);
        int restarts = getArgInt(argc, argv, "--restarts", 1000);
        int steps = getArgInt(argc, argv, "--steps", 5000);
        int seed = getArgInt(argc, argv, "--seed", 430055);
        int degreeTarget = getArgInt(argc, argv, "--degree-target", -1);
        int degreeWeight = getArgInt(argc, argv, "--degree-weight", 1);
        int target = getArgInt(argc, argv, "--target", 0);
        int tabuTenure = getArgInt(argc, argv, "--tabu", 9);

        if (input.empty() || outdir.empty()) {
            cerr << "Missing --input or --outdir\n";
            return 2;
        }

        vector<pair<int,string>> tokens = readTokens(input, limit);

        string resultsPath = outdir + "\\RESULTS_SHADOW_DELTA_FLIP_V07.tsv";
        string summaryPath = outdir + "\\SUMMARY_SHADOW_DELTA_FLIP_V07.txt";

        ofstream res(resultsPath);
        if (!res) throw runtime_error("cannot write results");

        res << "record_index\tline_number\tn\tred_pred\tblue_pred\tstatus\tbest_phi\tred_phi\tblue_phi\tdegree\trestart\tsteps\tchi\n";

        auto t0 = chrono::steady_clock::now();

        int idx = 0;
        int found = 0;

        for (auto& item : tokens) {
            idx++;
            Graph g = decodeGraph6(item.second);
            Hyper h = buildHyper(g, a, b);

            BestResult br = runHeuristic(
                h,
                restarts,
                steps,
                seed + idx * 1009,
                degreeTarget,
                degreeWeight,
                target,
                tabuTenure
            );

            if (br.status == "FOUND_TARGET") found++;

            res << idx << "\t"
                << item.first << "\t"
                << g.n << "\t"
                << h.red.size() << "\t"
                << h.blue.size() << "\t"
                << br.status << "\t"
                << br.bestPhi << "\t"
                << br.bestRedPhi << "\t"
                << br.bestBluePhi << "\t"
                << br.bestDegree << "\t"
                << br.restart << "\t"
                << br.steps << "\t"
                << br.chi << "\n";

            cout << "REC " << idx
                 << " line=" << item.first
                 << " n=" << g.n
                 << " redPred=" << h.red.size()
                 << " bluePred=" << h.blue.size()
                 << " bestPhi=" << br.bestPhi
                 << " red=" << br.bestRedPhi
                 << " blue=" << br.bestBluePhi
                 << " deg=" << br.bestDegree
                 << " status=" << br.status
                 << "\n";
        }

        auto t1 = chrono::steady_clock::now();
        double sec = chrono::duration<double>(t1 - t0).count();

        ofstream sum(summaryPath);
        sum << "MACHURA SHADOW DELTA-FLIP HEURISTIC V07\n";
        sum << "=======================================\n\n";
        sum << "INPUT: " << input << "\n";
        sum << "A: " << a << "\n";
        sum << "B: " << b << "\n";
        sum << "RECORDS: " << tokens.size() << "\n";
        sum << "RESTARTS: " << restarts << "\n";
        sum << "STEPS_PER_RESTART: " << steps << "\n";
        sum << "DEGREE_TARGET: " << degreeTarget << "\n";
        sum << "DEGREE_WEIGHT: " << degreeWeight << "\n";
        sum << "TARGET: " << target << "\n";
        sum << "TABU: " << tabuTenure << "\n";
        sum << "FOUND_TARGET_RECORDS: " << found << "\n";
        sum << "ELAPSED_SEC: " << sec << "\n\n";
        sum << "METHOD:\n";
        sum << "Precompute red K_{a-1} and blue K_{b-1} shadow hyperedges.\n";
        sum << "Maintain local counts under chi flips.\n";
        sum << "Use delta Phi, tabu, restart, shake, and optional degree target.\n";

        cout << "DONE\n";
        cout << "RESULTS: " << resultsPath << "\n";
        cout << "SUMMARY: " << summaryPath << "\n";
        cout << "ELAPSED_SEC: " << sec << "\n";
        cout << "FOUND_TARGET_RECORDS: " << found << "\n";

        return 0;
    } catch (const exception& e) {
        cerr << "ERROR: " << e.what() << "\n";
        return 1;
    }
}
