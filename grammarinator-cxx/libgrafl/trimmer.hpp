// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAFL_TRIMMER_HPP
#define GRAFL_TRIMMER_HPP

#include <algorithm>
#include <functional>
#include <map>
#include <set>
#include <vector>

// Reducers in the style of AFL++ trimmers


// Trimmer based on the Minimizing Delta Debugging algorithm.
// Works on configurations of so-called deltas, i.e., sets of units.
// Adds the concept of links between units: if a is linked to b and c, then
// whenever a is removed from the configuration, b and c are also removed.
// (This is an alternative, perhaps simpler approach to dealing with hierarchy
// between units.)
// Uses caching to prevent repeated tests of already seen configurations.
template<typename T>
class ConfigTrimmer {
public:
    using unit_type = T;
    using config_type = std::set<T>;
    using link_type = std::map<T, config_type>;

private:
    config_type config_;
    link_type links_;
    std::vector<config_type> subsets_;
    int i_;
    config_type next_config_;
    std::set<config_type> config_cache_;

public:
    // TODO: proper ctors and dtor

    // return 0 if the config cannot be trimmed at all, 1 otherwise
    int init(const config_type& config, const link_type& links = {}) {
        // set the configuration-to-be-reduced to the initial configuration
        // and clear the splitting
        // also save the linking information
        config_ = config;
        subsets_.clear();
        subsets_.push_back(config);
        links_ = links;

        config_cache_.clear();

        // compute the first configuration, if any, to be able to tell whether there are any trimming steps to be tried
        return next() ? 1 : 0;
    }

    // calling trim if init returned 0 is an error (there are no potential trimmed configurations of the initial configuration at all)
    // calling trim if post returned 1 is an error (all potential trimmed configurations have been already enumerated)
    // calling trim again without a call to post first is an error (without feedback on the success of the last trimmed configuration, the next potential trimmed configuration cannot be computed)
    const config_type& trim() {
        // almost a no-op, the next configuration to be tested has already been computed
        return next_config_;
    }

    // return 0 if there are still more steps to do, 1 otherwise
    // calling post again without a call to trim first is an error
    int post(bool success) {
        if (success) {
            // if the last configuration returned by trim was successful
            // std::cout << "trimmed" << std::endl;

            // evict cache entries that are bigger than the successful configuration
            int size = next_config_.size();
            for (auto it = config_cache_.begin(); it != config_cache_.end();) {
                if (it->size() >= size)
                    it = config_cache_.erase(it);
                else
                    ++it;
            }

            // set the configuration-to-be-reduced-further to the successful configuration
            // and clear the splitting
            config_ = next_config_;
            subsets_.clear();
            subsets_.push_back(config_);
        } else {
            // add unsuccessful configuration to the cache
            config_cache_.insert(next_config_);

            ++i_;
        }

        // compute the next configuration, if any, to be able to tell whether there are any further trimming steps
        return next() ? 0 : 1;
    }

private:
    // return true if a "next" configuration exists, false otherwise
    // also compute that "next" configuration at the same time
    bool next() {
        // empty or singleton sets cannot be reduced
        const int size = config_.size();
        if (size < 2)
            return false;

        // split the configuration into subsets if it hasn't been split yet
        // and reset the internal counter used to iterate over subsets and complement sets
        int n = subsets_.size();
        if (n < 2)
            n = split();

        while (true) {
            if (i_ < 2 * n) {
                // if the internal counter is still referring to the current subsets or complement sets
                if (i_ < n) {
                    // next configuration is going to be a subset
                    next_config_ = subsets_[i_];
                    // std::cout << "subset: size: " << size << ", n: " << n  << ", i_: " << i_ << std::endl;
                } else {
                    // next configuration is going to be a complement set
                    next_config_.clear();
                    int j = i_ - n;
                    for (int k = 0; k < n; ++k) {
                        if (k != j)
                            next_config_.insert(subsets_[k].begin(), subsets_[k].end());
                    }
                    // std::cout << "complement set: size: " << size << ", n: " << n  << ", j: " << j << std::endl;
                }
                // remove units linked to removed units
                unlink();
                // if configuration hasn't been seen yet, the computation of the next configuration is finished
                if (!config_cache_.contains(next_config_))
                    return true;
                // otherwise, skip this configuration, increment the internal counter, and try again
                // std::cout << "config cache hit" << std::endl;
                ++i_;
            } else if (n < size) {
                // if the internal counter is grown out of bounds, but the subsets can be still split further,
                // then increase the splitting and reset the internal counter
                // std::cout << "increase splitting" << std::endl;
                n = split();
            } else {
                // if the internal counter is grown out of bounds and all the subsets are singletons,
                // then every possible subconfiguration has been already tested at the finest splitting
                // and there is no possible next configuration
                // std::cout << "done" << std::endl;
                return false; //
            }
        }
    }

    // split the current configuration into subsets, or re-split into smaller subsets
    // fast, uses integer arithmetic only
    // return the new number of subsets
    int split() {
        int size = config_.size();
        int n = std::min<int>(size, subsets_.size() * 2); // the split factor is fixed to 2
        subsets_.clear();
        subsets_.resize(n);

        int d = 0;
        int i = 0;
        int j = 0;
        for (const auto& c : config_) {
            subsets_[j].insert(c);
            d += n;
            if (d >= size) {
                d -= size;
                j++;
            }
            i++;
        }

        i_ = 0;
        return n;
    }

    // follow links and remove units from the next configuration that are linked to units that have already been removed
    void unlink() {
        std::vector<T> worklist{};
        for (auto const& [e, linkeds] : links_)
            if (!next_config_.contains(e))
                worklist.push_back(e);
        while (!worklist.empty()) {
            auto e = worklist.back();
            worklist.pop_back();
            for (auto const& linked : links_[e]) {
                bool erased = next_config_.erase(linked);
                if (erased && links_.contains(linked))
                    worklist.push_back(linked);
            }
        }
    }
};


// Experimental content trimmer wrapping the config trimmer.
// Uses a serializer to create some representation of a configuration.
// Adds a second layer of caching to cache the serialized representation as well.
// The caching uses a hashing mechanism to avoid huge memory consumption.
template<typename T, typename O, typename H>
class ContentTrimmer {
public:
    using unit_type = typename ConfigTrimmer<T>::unit_type;
    using config_type = typename ConfigTrimmer<T>::config_type;
    using link_type = typename ConfigTrimmer<T>::link_type;
    using content_type = O;
    using serializer_type = std::function<content_type(const config_type&)>;
    using hash_type = H;
    using hasher_type = std::function<hash_type(const content_type&)>;

private:
    ConfigTrimmer<T> trimmer_;
    serializer_type serializer_;
    hasher_type hasher_;
    config_type next_config_;
    content_type next_content_;
    std::map<hash_type, int> content_cache_;

public:
    // TODO: proper ctors and dtor

    int init(const config_type& config, serializer_type serializer, hasher_type hasher, const link_type& links = {}) {
        if (trimmer_.init(config, links) < 1)
            return 0;

        serializer_ = serializer;
        hasher_ = hasher;

        content_cache_.clear();

        return next() ? 1 : 0;
    }

    const content_type& trim() {
        return next_content_;
    }

    const config_type& recall() {
        return next_config_;
    }

    int post(bool success) {
        int size = next_content_.size();
        if (success) {
            for (auto it = content_cache_.begin(); it != content_cache_.end();) {
                if (it->second > size) // FIXME: would >= be safe?
                    it = content_cache_.erase(it);
                else
                    ++it;
            }
        } else {
            content_cache_.emplace(hasher_(next_content_), size);
        }

        if (trimmer_.post(success) > 0)
            return 1;

        return next() ? 0 : 1;
    }

private:
    bool next() {
        while (true) {
            next_config_ = trimmer_.trim();
            next_content_ = serializer_(next_config_);

            if (!content_cache_.contains(hasher_(next_content_)))
                return true;

            // std::cout << "content cache hit" << std::endl;
            if (trimmer_.post(false) > 0)
                return false;
        }
    }
};

#endif // GRAFL_TRIMMER_HPP
