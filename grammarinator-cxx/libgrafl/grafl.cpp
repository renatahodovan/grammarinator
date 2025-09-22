// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#include "afl-fuzz.h"

#include "trimmer.hpp"

#include <grammarinator/runtime.hpp>
#include <grammarinator/tool.hpp>
#include <grammarinator/util/log.hpp>
#include <grammarinator/util/random.hpp>

#include <nlohmann/json.hpp>

#include <xxhash.h>

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include "grammarinator/config.hpp"

#ifndef GRAMMARINATOR_GENERATOR
#error "GRAMMARINATOR_GENERATOR must be defined"
#endif

using namespace grammarinator::runtime;

// ---- State ------------------------------------------------------------------

namespace {

struct grafl_state {
  afl_state_t* afl;

  // Tool specialized for the selected grammar.
  std::unique_ptr<grammarinator::tool::AFLTool<
    grammarinator::tool::DefaultGeneratorFactory<
      GRAMMARINATOR_GENERATOR,
      GRAMMARINATOR_MODEL,
      GRAMMARINATOR_LISTENER>>> tool;

  // Trees
  Rule* current_tree;
  Rule* mutated_tree;

  // Fuzz buffer
  std::vector<uint8_t> fuzz_buf;

  // Fuzz loop planning
  unsigned int fuzz_cnt;

  // Trimming
  ContentTrimmer<Rule*, std::string, XXH64_hash_t> trimmer;
  size_t trim_step, trim_max_steps;
  std::set<Rule*> trim_init_config;
  std::map<Rule*, std::set<Rule*>> trim_links;
  std::map<ParentRule*, std::vector<Rule*>> trim_saved_children;
  std::set<Rule*> trim_succ_config;
  std::vector<uint8_t> trim_buffer;
};

// ---- Helpers ------------------------------------------------------------

static unsigned int env_u32(const char* k, unsigned int dflt) {
  if (const char* v = std::getenv(k)) {
    char* endptr = nullptr;
    errno = 0;
    unsigned long x = std::strtoul(v, &endptr, 10);
    if (endptr == v || errno != 0) {
      return dflt;
    }
    return x ? static_cast<unsigned int>(x) : dflt;
  }
  return dflt;
}

static bool env_bool(const char* k, bool dflt) {
  if (const char* v = std::getenv(k)) {
    std::string s(v);
    for (auto &c : s) c = static_cast<char>(std::tolower(c));
    return s == "1" || s == "true" || s == "yes";
  }
  return dflt;
}

}  // anonymous namespace

// ---- AFL API functions------------------------------------------------------

/**
 * This method is called when AFL++ starts up and is used to seed RNG and set
 * up buffers and state.
 */
extern "C"
void* afl_custom_init(afl_state_t* afl, unsigned int seed) {
  grammarinator::util::random_engine.seed(seed);

  auto* st = new grafl_state();
  st->afl = afl;
  st->afl->afl_env.afl_post_process_keep_original = 1;
  st->fuzz_cnt = 0;
  st->trim_step = 0;
  st->current_tree = nullptr;
  st->mutated_tree = nullptr;

  // Buffers
  st->fuzz_buf.resize(1 * 1024 * 1024);

  // Env config (all GRAFL_*)
  const unsigned int max_depth = env_u32("GRAFL_MAX_DEPTH", 0);
  const unsigned int max_tokens = env_u32("GRAFL_MAX_TOKENS", 0);
  const unsigned int memo_size = env_u32("GRAFL_MEMO_SIZE", 0);
  const bool random_mut = env_bool("GRAFL_RANDOM_MUTATORS", true);
  st->trim_max_steps = env_u32("GRAFL_MAX_TRIM_STEPS", 200);

  WeightedModel::AltMap weights;
  WeightedModel::QuantMap probs;

  if (const char* weights_path = std::getenv("GRAFL_WEIGHTS")) {
    JsonWeightLoader().load(weights_path, weights, probs);
  }

  static const GRAMMARINATOR_TREECODEC treeCodec;
  RuleSize rule_size = RuleSize(
    max_depth > 0 ? max_depth : RuleSize::max().depth,
    max_tokens > 0 ? max_tokens : RuleSize::max().tokens
  );

  std::vector<Rule* (*)(Rule*)> transformers =
    GRAMMARINATOR_TRANSFORMER
      ? std::vector<Rule* (*)(Rule*)>{GRAMMARINATOR_TRANSFORMER}
      : std::vector<Rule* (*)(Rule*)>{};

  grammarinator::tool::DefaultGeneratorFactory<GRAMMARINATOR_GENERATOR, GRAMMARINATOR_MODEL, GRAMMARINATOR_LISTENER> factory(weights, probs);
  st->tool = std::make_unique<grammarinator::tool::AFLTool<grammarinator::tool::DefaultGeneratorFactory<GRAMMARINATOR_GENERATOR, GRAMMARINATOR_MODEL, GRAMMARINATOR_LISTENER>>>(
    factory, GRAMMARINATOR_GENERATOR::_default_rule, rule_size,
    random_mut, std::unordered_set<std::string>{}, std::unordered_set<std::string>{},
    transformers, GRAMMARINATOR_SERIALIZER,
    memo_size, treeCodec
  );

  return st;
}

/**
 * The last method to be called, deinitializing the state.
 */
extern "C"
void afl_custom_deinit(void* data) {
  auto* st = static_cast<grafl_state*>(data);
  if (!st) {
    return;
  }
  delete st->current_tree;
  delete st->mutated_tree;
  delete st;
}

/**
 * When a queue entry is selected to be fuzzed, afl-fuzz selects the number of
 * fuzzing attempts with this input based on a few factors. If, however, the
 * custom mutator wants to set this number instead on how often it is called
 * for a specific queue entry, use this function. This function is most useful
 * if AFL_CUSTOM_MUTATOR_ONLY is not used.
 */
// Use AFL's fuzz count metric, but avoid incrementing it in case of new founds.
extern "C"
unsigned int afl_custom_fuzz_count(void* data, const unsigned char*, size_t) {
  auto* st = static_cast<grafl_state*>(data);
  return st->afl->stage_max;
}

/**
 * This method determines whether AFL++ should fuzz the current queue entry or
 * not: all defined custom mutators as well as all AFL++'s mutators.
 */
extern "C"
unsigned char afl_custom_queue_get(void* data, const unsigned char* filename) {
  auto* st = static_cast<grafl_state*>(data);
  if (!filename) {
    return 0;
  }
  std::string fn = reinterpret_cast<const char*>(filename);

  // Read encoded tree from file.
  std::vector<uint8_t> encoded_tree;
  std::error_code ec;
  auto fsize = std::filesystem::file_size(fn, ec);
  if (ec) {
    return 0;
  }

  // Skip too large test cases since they will be truncated and cannot be
  // decoded anyway.
  if (fsize > st->afl->max_length) {
    GRAMMARINATOR_LOG_WARN("{} is larger than max_length ({} > {}). Skipping.", fn, fsize, st->afl->max_length);
    return 0;
  }

  FILE* f = std::fopen(fn.c_str(), "rb");
  if (!f) {
    return 0;
  }
  encoded_tree.resize(fsize);
  size_t n = std::fread(encoded_tree.data(), 1, encoded_tree.size(), f);
  std::fclose(f);
  if (n != encoded_tree.size()) {
    return 0;
  }

  // Build tree from the encoded representation
  Rule* root = st->tool->decode(encoded_tree.data(), encoded_tree.size());
  if (!root) {
    return 0;
  }

  delete st->current_tree;
  st->current_tree = root;
  //st->tool->save_tree(root);
  return 1;
}

/**
 * This methods is called after adding a new test case to the queue. If the
 * contents of the file was changed, return True, False otherwise.
 */
extern "C"
u8 afl_custom_queue_new_entry(void *data, const unsigned char *filename_new_queue, const unsigned int *filename_orig_queue) {
  auto* st = static_cast<grafl_state*>(data);
  st->tool->save_tree(st->current_tree);
  return 0;
}

/**
 * If this function is present, no splicing target is passed to the fuzz
 * function. This saves time if splicing data is not needed by the custom
 * fuzzing function. This function is never called, just needs to be
 * present to activate.
 */
// Note: we don't use the donor provided by AFL, since its a raw source
// instead of a tree representation that would be very expensive to parse.
extern "C"
void afl_custom_splice_optout(void *data) {
}

/**
 * This method performs your custom mutations on a given input. The add_buf is
 * the contents of another queue item that can be used for splicing - or
 * anything else - and can also be ignored. If you are not using this
 * additional data then define splice_optout (see above). This function is
 * optional. Returning a length of 0 is valid and is interpreted as skipping
 * this one mutation result. For non-Python: the returned output buffer is
 * under your memory management!
 */
extern "C"
size_t afl_custom_fuzz(void* data, unsigned char*, size_t,
                       unsigned char** out_buf, unsigned char* add_buf,
                       size_t add_buf_size, size_t max_size) {
  auto* st = static_cast<grafl_state*>(data);
  if (!st->current_tree) {
    *out_buf = nullptr;
    return 0;
  }

  delete st->mutated_tree;
  st->mutated_tree = st->current_tree->clone();
  Individual individual(st->mutated_tree, false);
  auto mutated_tree = st->tool->mutate(&individual);
  if (!mutated_tree) {
    return 0;
  }
  st->mutated_tree = mutated_tree;

  std::vector<uint8_t> out = st->tool->encode(st->mutated_tree);
  size_t n = out.size();
  if (n > max_size) {
    return 0;
  }

  if (!st->tool->memoize_test(out.data(), out.size())) {
    // TODO: memo size is missing from the next message but it's only available from Tool.
    GRAMMARINATOR_LOG_DEBUG("Mutation attempt: already generated among the last N unique test cases");
    GRAMMARINATOR_LOG_TRACE("Duplicate test case: {}", st->tool->serializer(st->mutated_tree));
    return 0;
  }

  st->fuzz_cnt++;
  st->fuzz_buf = out;
  *out_buf = st->fuzz_buf.data();
  return n;
}

/**
 * This method is called at the start of each trimming operation and receives
 * the initial buffer. It should return the amount of iteration steps possible
 * on this input (e.g., if your input has n elements and you want to remove
 * them one by one, return n, if you do a binary search, return log(n), and
 * so on).
 *
 * If your trimming algorithm doesn't allow to determine the amount of
 * (remaining) steps easily (esp. while running), then you can alternatively
 * return 1 here and always return 0 in post_trim until you are finished and
 * no steps remain. In that case, returning 1 in post_trim will end the
 * trimming routine. The whole current index/max iterations stuff is only used
 * to show progress.
 */
extern "C"
int afl_custom_init_trim(void* data, unsigned char* buf, size_t size) {
  auto st = static_cast<grafl_state*>(data);

  if (!st->current_tree) {
    // This happens if custom trim is used from afl-tmin.
    st->current_tree = st->tool->decode(buf, size);
  }
  st->trim_step = 1;

  // collect information about the quantified nodes:
  // the nodes themselves,
  // the ancestor-descendant relationships between them, and
  // their position among the children of their quantifier parent nodes
  st->trim_init_config.clear();
  st->trim_links.clear();
  st->trim_saved_children.clear();

  auto collector = [st](const auto& self, Rule* node, Rule* quantified_ancestor = nullptr) -> void {
    if (node->type == Rule::RuleType::UnparserRuleQuantifiedType) {
      st->trim_init_config.insert(node);
      if (quantified_ancestor) {
        st->trim_links[quantified_ancestor].insert(node);
      }
      quantified_ancestor = node;
      st->trim_saved_children.try_emplace(node->parent, node->parent->children);
    }
    if (node->type != Rule::RuleType::UnlexerRuleType) {
      auto node_as_parent = static_cast<ParentRule*>(node);
      for (auto child : node_as_parent->children)
        self(self, child, quantified_ancestor);
    }
  };
  collector(collector, st->current_tree);

  st->trim_succ_config = st->trim_init_config;

  // define the serializer
  // first, temporarily but actually remove the quantified nodes from the tree
  // thus hiding it from the serializer,
  // then, after the serializer finished, reset the tree to contain all the initial quantified nodes
  // (!!! all this is done by messing with the internals of the tree, not using API methods !!!)
  auto serializer = [st](const std::set<Rule*>& trimmed_config) {
    std::set<Rule*> removed_config;
    std::set_difference(st->trim_init_config.begin(), st->trim_init_config.end(),
                        trimmed_config.begin(), trimmed_config.end(),
                        std::inserter(removed_config, removed_config.end()));
    std::set<ParentRule*> removed_parents;
    for (auto removed_node : removed_config) {
      // DANGER: we don't delete these nodes, nor do we set their parent to nullptr
      removed_node->parent->children.erase(std::find(removed_node->parent->children.begin(),
                                                     removed_node->parent->children.end(), removed_node));
      removed_parents.insert(removed_node->parent);
    }
    auto out_vec = st->tool->encode(st->current_tree);
    // TODO: is this string conversion correct/appropriate?
    std::string s(reinterpret_cast<const char*>(out_vec.data()), out_vec.size());
    for (auto removed_parent : removed_parents) {
      // DANGER: another black magic, we reset the children to a saved state
      removed_parent->children = st->trim_saved_children.at(removed_parent);
    }
    return s;
  };

  GRAMMARINATOR_LOG_TRACE("INIT TRIM [{}]: {}...", st->trim_init_config.size(), st->tool->serializer(st->current_tree));

  // define the hasher
  auto hasher = [](const std::string& s) { return XXH3_64bits(s.data(), s.length()); };
  return st->trimmer.init(st->trim_init_config, serializer, hasher, st->trim_links);
}

/**
 * This method is called for each trimming operation. It doesn't have any
 * arguments because there is already the initial buffer from init_trim and we
 * can memorize the current state in the data variables. This can also save
 * reparsing steps for each iteration. It should return the trimmed input
 * buffer.
 */
extern "C"
size_t afl_custom_trim(void* data, unsigned char** out_buf) {
  auto st = static_cast<grafl_state*>(data);

  auto s = st->trimmer.trim();
  size_t len = s.length();
  GRAMMARINATOR_LOG_TRACE("TRIM #{} [{}]", st->trim_step, st->trimmer.recall().size());

  // reserve large enough memory for trim_buffer
  if (st->trim_buffer.size() < len) {
    st->trim_buffer.resize(len);
  }

  // return trim_buffer via out_buffer, and the length of the data in trim_buffer
  *out_buf = st->trim_buffer.data();
  if (*out_buf) {
    std::memcpy(*out_buf, s.data(), len);
  }
  return len;
}

/**
 * This method is called after each trim operation to inform you if your
 * trimming step was successful or not (in terms of coverage). If you receive
 * a failure here, you should reset your input to the last known good state.
 * In any case, this method must return the next trim iteration index (from 0
 * to the maximum amount of steps you returned in init_trim).
 */
extern "C"
int afl_custom_post_trim(void* data, unsigned char success) {
  auto st = static_cast<grafl_state*>(data);

  if (success) {
    GRAMMARINATOR_LOG_TRACE("POST TRIM #{} [{}]: success!", st->trim_step, st->trimmer.recall().size());
    st->trim_succ_config = st->trimmer.recall();
  }

  int post_result;
  if (st->trim_step >= st->trim_max_steps) {
    GRAMMARINATOR_LOG_TRACE("POST TRIM #{}: step limit reached", st->trim_step);
    post_result = 1;
  } else {
    post_result = st->trimmer.post(success);
    if (post_result > 0) {
      GRAMMARINATOR_LOG_TRACE("POST TRIM #{}: completed", st->trim_step);
    } else
      st->trim_step++;
  }
  if (post_result > 0) {
    // end of trimming, commit changes (which have been only in the form of configurations, until now) to the tree
    std::set<Rule*> removed_config;
    std::set_difference(st->trim_init_config.begin(), st->trim_init_config.end(),
                        st->trim_succ_config.begin(), st->trim_succ_config.end(),
                        std::inserter(removed_config, removed_config.end()));
    for (auto removed_node : removed_config)
      removed_node->remove(); // first, detach all removed nodes from their parents
    for (auto removed_node : removed_config)
      delete removed_node; // only delete nodes once all of them are detached: this way the order of deletion does not matter
    GRAMMARINATOR_LOG_INFO("POST TRIM [{}->{}]: {}", st->trim_init_config.size(), st->trim_succ_config.size(), st->tool->serializer(st->current_tree));

    // Save the trimmed tree to SubTreePopulation.
    st->tool->save_tree(st->current_tree);
  }
  return post_result;
}

// This is only used from afl-tmin at the very first execution to create executable test case from
// the encoded tree representation.
extern "C"
size_t afl_custom_post_process(void *data, unsigned char *buf, size_t buf_size, unsigned char **out_buf) {
  auto* st = static_cast<grafl_state*>(data);

  // If the size of the current buffer equals with exactly the max_length, then it's most probabl truncated.
  if (buf_size == st->afl->max_length) {
    GRAMMARINATOR_LOG_WARN("Test case is probably truncated in post process. Skipping it.");
    *out_buf = buf;
    return buf_size;
  }

  Rule* root = st->tool->decode(buf, buf_size);
  if (root) {
    std::string out = st->tool->serializer(root);
    GRAMMARINATOR_LOG_TRACE("# {}. test:\n{}\n----------------------\n", st->fuzz_cnt, out);
    delete root;

    unsigned char *nbuf = (unsigned char *)std::malloc(out.size());
    if (!nbuf && out.size() > 0) {
      *out_buf = buf;
      return buf_size;
    }

    if (out.size() > 0) {
      std::memcpy(nbuf, out.data(), out.size());
    }
    *out_buf = nbuf;
    return out.size();
  }

  *out_buf = buf;
  return buf_size;
}

/**
 * This method is called after a new queue entry, crash or timeout is
 * discovered if compiled with INTROSPECTION. The custom mutator can then
 * return a string (const char *) that reports the exact mutations used.
 */
extern "C"
const char* afl_custom_introspection(void* data) {
  auto* st = static_cast<grafl_state*>(data);
  return st->tool->last_mutator.c_str();
}

/**
 * When this function is called, it shall describe the current test case,
 * generated by the last mutation. This will be called, for example, to name
 * the written test case file after a crash occurred. Using it can help to
 * reproduce crashing mutations.
 */
extern "C"
const char *afl_custom_describe(void *data, size_t max_description_len) {
  auto* st = static_cast<grafl_state*>(data);
  if (!st || st->tool->last_mutator.empty()) {
    return "grafl"; // fallback, if there is not mutator name set.
  }

  // AFL++ expects a null-terminated string, truncated if too long.
  if (st->tool->last_mutator.size() >= max_description_len) {
    st->tool->last_mutator.resize(max_description_len - 1);
  }

  return st->tool->last_mutator.c_str();
}
