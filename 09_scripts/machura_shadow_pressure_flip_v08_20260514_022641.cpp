#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
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
    int kr = 0;
    int kb = 0;
    vector<uint64_t> red;
    vector<uint64_t> blue;
    vector<vector<int>> redInc;
    vector<vector<int>> blueInc;
};

struct State {
    vector<unsigned char> x;
    vector<int> redCnt;
    vector<int> blueCnt;
    int degree = 0;
    int redPhi = 0;
    int bluePhi = 0;
    int phi = 0;
    long long energy = 0;
};

struct Params {
    int a = 5;
    int b = 5;
    int restarts = 500;
    int steps = 2000;
    int seed = 430055;
    int target = 2;
    int degreeTarget = 21;
    int tabu = 9;
    long long wPhi = 1000000000LL;
    long long wNear1 = 1000000LL;
    long long wNear2 = 1000LL;
    long long wDegree = 100LL;
    int shakeAfter = 250;
};

struct Best {
    int bestPhi = 1000000000;
    int redPhi = 0;
    int bluePhi = 0;
    int degree = 0;
    int restart = -1;
    long long step = 0;
    long long totalSteps = 0;
    long long energy = 0;
    string chi;
    string status = "SEARCH_DONE";
};

static string trim(const string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

static Graph decodeGraph6(string s) {
    s = trim(s);
    string pref = ">>graph6<<";
    if (s.rfind(pref, 0) == 0) s = s.substr(pref.size());

    vector<int> vals;
    for (char c : s) vals.push_back((int)c - 63);
    if (vals.empty()) throw runtime_error("empty graph6");

    int n = 0, pos = 1;
    if (vals[0] <= 62) {
        n = vals[0];
    } else if (vals[0] == 63) {
        if ((int)vals.size() < 4) throw runtime_error("bad graph6 n");
        n = (vals[1] << 12) | (vals[2] << 6) | vals[3];
        pos = 4;
    } else {
        throw runtime_error("unsupported graph6 n");
    }

    if (n > 62) throw runtime_error("n > 62 unsupported");

    int need = n * (n - 1) / 2;
    vector<int> bits;
    for (int i = pos; i < (int)vals.size(); i++) {
        for (int k = 5; k >= 0; k--) bits.push_back((vals[i] >> k) & 1);
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

static bool redClique(const Graph& g, const vector<int>& c) {
    for (int i = 0; i < (int)c.size(); i++)
        for (int j = i + 1; j < (int)c.size(); j++)
            if (!g.adj[c[i]][c[j]]) return false;
    return true;
}

static bool blueClique(const Graph& g, const vector<int>& c) {
    for (int i = 0; i < (int)c.size(); i++)
        for (int j = i + 1; j < (int)c.size(); j++)
            if (g.adj[c[i]][c[j]]) return false;
    return true;
}

static uint64_t maskOf(const vector<int>& c) {
    uint64_t m = 0;
    for (int v : c) m |= (1ULL << v);
    return m;
}

static void genComb(int n, int k, int start, vector<int>& cur, const Graph& g, bool red, vector<uint64_t>& out) {
    if ((int)cur.size() == k) {
        if (red ? redClique(g, cur) : blueClique(g, cur)) out.push_back(maskOf(cur));
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
    h.kr = a - 1;
    h.kb = b - 1;
    h.redInc.assign(g.n, {});
    h.blueInc.assign(g.n, {});

    vector<int> cur;
    genComb(g.n, h.kr, 0, cur, g, true, h.red);
    cur.clear();
    genComb(g.n, h.kb, 0, cur, g, false, h.blue);

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

static long long edgePressure(int cnt, int k, const Params& p) {
    if (cnt >= k) return p.wPhi;
    if (cnt == k - 1) return p.wNear1;
    if (cnt == k - 2) return p.wNear2;
    return 0;
}

static int degPenalty(int d, int target) {
    if (target < 0) return 0;
    return abs(d - target);
}

static long long computeEnergy(const Hyper& h, const State& s, const Params& p) {
    long long e = 0;
    for (int c : s.redCnt) e += edgePressure(c, h.kr, p);
    for (int c : s.blueCnt) e += edgePressure(c, h.kb, p);
    e += p.wDegree * degPenalty(s.degree, p.degreeTarget);
    return e;
}

static State initState(const Hyper& h, mt19937_64& rng, const Params& p) {
    State s;
    s.x.assign(h.n, 0);
    s.redCnt.assign(h.red.size(), 0);
    s.blueCnt.assign(h.blue.size(), 0);

    vector<int> perm(h.n);
    iota(perm.begin(), perm.end(), 0);
    shuffle(perm.begin(), perm.end(), rng);

    if (p.degreeTarget >= 0 && p.degreeTarget <= h.n) {
        for (int i = 0; i < p.degreeTarget; i++) s.x[perm[i]] = 1;
    } else {
        for (int i = 0; i < h.n; i++) s.x[i] = (unsigned char)(rng() & 1ULL);
    }

    for (int v = 0; v < h.n; v++) if (s.x[v]) s.degree++;

    for (int e = 0; e < (int)h.red.size(); e++) {
        uint64_t m = h.red[e];
        int c = 0;
        for (int v = 0; v < h.n; v++) if (((m >> v) & 1ULL) && s.x[v]) c++;
        s.redCnt[e] = c;
        if (c == h.kr) s.redPhi++;
    }

    for (int e = 0; e < (int)h.blue.size(); e++) {
        uint64_t m = h.blue[e];
        int c = 0;
        for (int v = 0; v < h.n; v++) if (((m >> v) & 1ULL) && !s.x[v]) c++;
        s.blueCnt[e] = c;
        if (c == h.kb) s.bluePhi++;
    }

    s.phi = s.redPhi + s.bluePhi;
    s.energy = computeEnergy(h, s, p);
    return s;
}

struct Delta {
    long long dEnergy = 0;
    int dRedPhi = 0;
    int dBluePhi = 0;
    int dPhi = 0;
    int dDegree = 0;
};

static Delta calcDelta(const Hyper& h, const State& s, int v, const Params& p) {
    Delta d;
    int old = s.x[v] ? 1 : 0;
    d.dDegree = old ? -1 : 1;

    for (int e : h.redInc[v]) {
        int before = s.redCnt[e];
        int after = before + (old ? -1 : 1);

        d.dEnergy += edgePressure(after, h.kr, p) - edgePressure(before, h.kr, p);
        d.dRedPhi += (after == h.kr ? 1 : 0) - (before == h.kr ? 1 : 0);
    }

    for (int e : h.blueInc[v]) {
        int before = s.blueCnt[e];
        int after = before + (old ? 1 : -1);

        d.dEnergy += edgePressure(after, h.kb, p) - edgePressure(before, h.kb, p);
        d.dBluePhi += (after == h.kb ? 1 : 0) - (before == h.kb ? 1 : 0);
    }

    int p0 = degPenalty(s.degree, p.degreeTarget);
    int p1 = degPenalty(s.degree + d.dDegree, p.degreeTarget);
    d.dEnergy += p.wDegree * (p1 - p0);

    d.dPhi = d.dRedPhi + d.dBluePhi;
    return d;
}

static void applyFlip(const Hyper& h, State& s, int v, const Delta& d) {
    int old = s.x[v] ? 1 : 0;

    for (int e : h.redInc[v]) s.redCnt[e] += old ? -1 : 1;
    for (int e : h.blueInc[v]) s.blueCnt[e] += old ? 1 : -1;

    s.x[v] = old ? 0 : 1;
    s.degree += d.dDegree;
    s.redPhi += d.dRedPhi;
    s.bluePhi += d.dBluePhi;
    s.phi += d.dPhi;
    s.energy += d.dEnergy;
}

static string chiString(const State& s) {
    string out;
    out.reserve(s.x.size());
    for (auto c : s.x) out.push_back(c ? '1' : '0');
    return out;
}

static Best runSearch(const Hyper& h, const Params& p, int recordSeed) {
    mt19937_64 rng((uint64_t)recordSeed);
    Best best;

    for (int r = 0; r < p.restarts; r++) {
        State s = initState(h, rng, p);
        vector<int> tabu(h.n, -1000000000);
        int noImprove = 0;

        for (int step = 0; step < p.steps; step++) {
            best.totalSteps++;

            if (s.phi < best.bestPhi) {
                best.bestPhi = s.phi;
                best.redPhi = s.redPhi;
                best.bluePhi = s.bluePhi;
                best.degree = s.degree;
                best.restart = r;
                best.step = step;
                best.energy = s.energy;
                best.chi = chiString(s);
                noImprove = 0;
            } else {
                noImprove++;
            }

            if (s.phi <= p.target) {
                best.status = "FOUND_TARGET";
                return best;
            }

            long long bestDE = 9223372036854775807LL;
            vector<int> cand;
            vector<Delta> candD;

            for (int v = 0; v < h.n; v++) {
                Delta d = calcDelta(h, s, v, p);
                bool isTabu = step < tabu[v];
                bool aspiration = s.phi + d.dPhi < best.bestPhi;

                if (isTabu && !aspiration) continue;

                if (d.dEnergy < bestDE) {
                    bestDE = d.dEnergy;
                    cand.clear();
                    candD.clear();
                    cand.push_back(v);
                    candD.push_back(d);
                } else if (d.dEnergy == bestDE) {
                    cand.push_back(v);
                    candD.push_back(d);
                }
            }

            if (cand.empty()) {
                for (int v = 0; v < h.n; v++) {
                    Delta d = calcDelta(h, s, v, p);
                    if (d.dEnergy < bestDE) {
                        bestDE = d.dEnergy;
                        cand.clear();
                        candD.clear();
                        cand.push_back(v);
                        candD.push_back(d);
                    } else if (d.dEnergy == bestDE) {
                        cand.push_back(v);
                        candD.push_back(d);
                    }
                }
            }

            if (cand.empty()) break;

            bool shake = (noImprove >= p.shakeAfter && bestDE >= 0);
            if (shake) {
                int flips = 4 + (int)(rng() % 9);
                for (int z = 0; z < flips; z++) {
                    int v = (int)(rng() % h.n);
                    Delta d = calcDelta(h, s, v, p);
                    applyFlip(h, s, v, d);
                    tabu[v] = step + p.tabu + (int)(rng() % 5);
                }
                noImprove = 0;
            } else {
                int pick = (int)(rng() % cand.size());
                int v = cand[pick];
                Delta d = candD[pick];
                applyFlip(h, s, v, d);
                tabu[v] = step + p.tabu + (int)(rng() % 5);
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
        if (line.empty() || line[0] == '#') continue;

        string token;
        stringstream ss(line);
        ss >> token;
        out.push_back({lineno, token});

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
        p.a = argi(argc, argv, "--a", 5);
        p.b = argi(argc, argv, "--b", 5);
        p.restarts = argi(argc, argv, "--restarts", 500);
        p.steps = argi(argc, argv, "--steps", 2000);
        p.seed = argi(argc, argv, "--seed", 430055);
        p.target = argi(argc, argv, "--target", 2);
        p.degreeTarget = argi(argc, argv, "--degree-target", 21);
        p.tabu = argi(argc, argv, "--tabu", 11);
        p.wPhi = argll(argc, argv, "--w-phi", 1000000000LL);
        p.wNear1 = argll(argc, argv, "--w-near1", 1000000LL);
        p.wNear2 = argll(argc, argv, "--w-near2", 1000LL);
        p.wDegree = argll(argc, argv, "--w-degree", 100LL);
        p.shakeAfter = argi(argc, argv, "--shake-after", 250);

        int limit = argi(argc, argv, "--limit", 0);

        vector<pair<int,string>> tokens = readTokens(input, limit);

        string resultsPath = outdir + "\\RESULTS_SHADOW_PRESSURE_FLIP_V08.tsv";
        string summaryPath = outdir + "\\SUMMARY_SHADOW_PRESSURE_FLIP_V08.txt";

        ofstream res(resultsPath);
        if (!res) throw runtime_error("cannot write results");

        res << "record_index\tline_number\tn\tred_pred\tblue_pred\tstatus\tbest_phi\tred_phi\tblue_phi\tdegree\trestart\tstep\ttotal_steps\tenergy\tchi\n";

        int idx = 0;
        int found = 0;
        int globalBest = 1000000000;

        auto t0 = chrono::steady_clock::now();

        for (auto& item : tokens) {
            idx++;

            Graph g = decodeGraph6(item.second);
            Hyper h = buildHyper(g, p.a, p.b);
            Best b = runSearch(h, p, p.seed + idx * 1009);

            if (b.status == "FOUND_TARGET") found++;
            globalBest = min(globalBest, b.bestPhi);

            res << idx << "\t"
                << item.first << "\t"
                << g.n << "\t"
                << h.red.size() << "\t"
                << h.blue.size() << "\t"
                << b.status << "\t"
                << b.bestPhi << "\t"
                << b.redPhi << "\t"
                << b.bluePhi << "\t"
                << b.degree << "\t"
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
                 << " bestPhi=" << b.bestPhi
                 << " red=" << b.redPhi
                 << " blue=" << b.bluePhi
                 << " deg=" << b.degree
                 << " status=" << b.status
                 << " steps=" << b.totalSteps
                 << "\n";
        }

        auto t1 = chrono::steady_clock::now();
        double sec = chrono::duration<double>(t1 - t0).count();

        ofstream sum(summaryPath);
        sum << "MACHURA SHADOW PRESSURE-FLIP HEURISTIC V08\n";
        sum << "==========================================\n\n";
        sum << "INPUT: " << input << "\n";
        sum << "RECORDS: " << tokens.size() << "\n";
        sum << "A: " << p.a << "\n";
        sum << "B: " << p.b << "\n";
        sum << "RESTARTS: " << p.restarts << "\n";
        sum << "STEPS: " << p.steps << "\n";
        sum << "TARGET: " << p.target << "\n";
        sum << "DEGREE_TARGET: " << p.degreeTarget << "\n";
        sum << "W_PHI: " << p.wPhi << "\n";
        sum << "W_NEAR1: " << p.wNear1 << "\n";
        sum << "W_NEAR2: " << p.wNear2 << "\n";
        sum << "W_DEGREE: " << p.wDegree << "\n";
        sum << "FOUND_TARGET_RECORDS: " << found << "\n";
        sum << "GLOBAL_BEST_PHI: " << globalBest << "\n";
        sum << "ELAPSED_SEC: " << sec << "\n\n";
        sum << "METHOD:\n";
        sum << "Energy uses completed shadow plus near-shadow pressure.\n";
        sum << "Moves are selected by local delta energy, while success is measured by true Phi.\n";

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
