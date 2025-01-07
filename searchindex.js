Search.setIndex({"docnames": ["concepts", "datatypes-api-reference", "high-level-arch", "index", "inference-api-reference", "model-parallel-api-reference", "modules-api-reference", "overview", "planner-api-reference", "setup-torchrec"], "filenames": ["concepts.rst", "datatypes-api-reference.rst", "high-level-arch.rst", "index.rst", "inference-api-reference.rst", "model-parallel-api-reference.rst", "modules-api-reference.rst", "overview.rst", "planner-api-reference.rst", "setup-torchrec.rst"], "titles": ["TorchRec Concepts", "Data Types", "TorchRec High Level Architecture", "Welcome to the TorchRec documentation!", "Inference", "Model Parallel", "Modules", "TorchRec Overview", "Planner", "Setting up TorchRec"], "terms": {"recommendation system": [0, 2, 3], "distributed train": [0, 2, 3], "embedding bag": 0, "embed": [0, 1, 3, 6, 7, 8, 9], "row wis": 0, "table wis": 0, "column wis": 0, "table row wis": 0, "sharder": [0, 4, 5, 8], "In": [0, 1, 2, 8, 9], "thi": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], "section": [0, 1, 2, 3, 9], "we": [0, 1, 2, 3, 6, 9], "learn": [0, 2, 3], "about": [0, 2], "kei": [0, 1, 5, 6, 8], "design": [0, 2, 5, 7], "larg": [0, 2, 3, 7, 8], "scale": [0, 2, 3, 7], "recommend": [0, 2, 3, 7], "system": [0, 2, 3, 7, 8], "us": [0, 1, 2, 3, 4, 5, 6, 8, 9], "pytorch": [0, 1, 2, 3, 7, 9], "how": [0, 2, 9], "each": [0, 1, 2, 6, 8], "work": [0, 1, 9], "detail": [0, 2, 8], "review": [0, 3], "rest": 0, "ha": [0, 1, 2, 5], "specif": [0, 7, 9], "input": [0, 1, 6, 8], "output": [0, 1, 2, 6, 8, 9], "data": [0, 2, 5, 6, 8, 9], "type": [0, 2, 4, 5, 6, 8, 9], "its": [0, 1, 4, 5, 6, 8], "effici": [0, 2, 7], "repres": [0, 1, 2, 6], "spars": [0, 1, 6, 9], "featur": [0, 1, 2, 3, 4, 6, 7, 8], "includ": [0, 1, 5], "wrapper": [0, 5], "around": 0, "length": [0, 1, 6, 9], "offset": [0, 1, 6], "valu": [0, 1, 6, 8, 9], "tensor": [0, 1, 5, 6, 8, 9], "singular": 0, "multipl": [0, 2, 5, 8], "can": [0, 1, 2, 3, 4, 5, 7], "think": 0, "s": [0, 1, 3, 5, 6, 8, 9], "keyedtensor": [0, 1, 6, 9], "torch": [0, 1, 4, 5, 6, 8, 9], "allow": [0, 1, 2, 7], "access": [0, 1, 2, 5], "through": [0, 2, 3, 6], "With": 0, "goal": 0, "high": 0, "perform": [0, 1, 2, 5, 6, 8], "canon": 0, "highli": 0, "ineffici": 0, "introduc": [0, 2], "new": [0, 3, 5, 9], "becaus": [0, 8], "thei": [0, 1, 5, 8], "provid": [0, 2, 4, 5, 7, 8], "storag": [0, 1, 8], "represent": [0, 1, 8], "As": [0, 2], "you": [0, 1, 2, 3, 9], "later": [0, 2], "make": [0, 1, 3], "commun": [0, 3, 7, 8], "environ": [0, 3, 4, 5, 7, 9], "veri": 0, "lead": 0, "one": [0, 2, 5], "advantag": 0, "end": [0, 2, 5, 8], "loop": 0, "compris": [0, 8], "follow": [0, 1, 3, 4, 6, 7], "main": [0, 2, 3, 5, 8], "compon": [0, 2, 7], "take": [0, 5, 6, 8], "configur": 0, "tabl": [0, 1, 3, 4, 6, 7, 8, 9], "setup": [0, 3], "gener": [0, 1, 2, 4, 7, 8, 9], "an": [0, 1, 2, 3, 4, 5, 6, 8, 9], "plan": [0, 2, 4, 5, 7, 8], "model": [0, 4, 7, 8], "accord": [0, 8], "differ": [0, 1, 2], "strategi": [0, 8], "parallel": [0, 7], "wise": [0, 7], "row": [0, 2, 7], "column": [0, 7], "combin": [0, 2], "entri": [0, 5], "point": [0, 5], "manner": 0, "A": [0, 1, 3], "It": [0, 2, 5, 6], "call": [0, 1, 2, 4, 5, 8, 9], "jag": [0, 1, 6], "variabl": [0, 1, 6], "sequenc": 0, "contrast": 0, "assum": [0, 6], "same": [0, 1, 5], "which": [0, 1, 2, 4, 5, 6, 7, 9], "often": [0, 2], "case": [0, 1], "real": [0, 2, 3, 8], "world": 0, "facilit": 0, "without": [0, 1], "pad": [0, 1], "list": [0, 1, 4, 5, 6, 8], "integ": [0, 6], "number": [0, 1, 2, 4, 6, 8, 9], "element": 0, "entiti": [0, 2], "start": [0, 1], "index": [0, 1, 6, 9], "flatten": 0, "These": [0, 6], "altern": 0, "1d": 0, "contain": [0, 1, 2, 5], "actual": 0, "store": [0, 1, 2], "contigu": 0, "here": [0, 2, 3], "simpl": [0, 7], "exampl": [0, 1, 3, 4, 5, 6, 8], "demonstr": [0, 9], "would": [0, 1], "look": [0, 2], "like": [0, 1, 2, 4, 5, 8], "user": [0, 2, 5, 8, 9], "interact": [0, 3], "1": [0, 1, 2, 4, 5, 6, 8, 9], "2": [0, 1, 2, 6, 8, 9], "item": 0, "3": [0, 1, 6, 8, 9], "0": [0, 1, 5, 6, 8, 9], "5": [0, 1, 6, 9], "101": 0, "102": 0, "201": 0, "202": 0, "203": 0, "301": 0, "id": [0, 2, 8], "jt": [0, 1], "OR": 0, "extend": [0, 7], "function": [0, 1, 5, 6, 8], "ar": [0, 1, 2, 3, 5, 6, 7, 8, 9], "typic": [0, 1, 8], "name": [0, 4, 5, 6, 8, 9], "label": 0, "group": [0, 1, 5, 8], "forward": [0, 2, 5, 6, 8, 9], "embeddingbagcollect": [0, 2, 4, 5, 6, 8, 9], "embeddingcollect": [0, 2, 4, 6], "impli": 0, "batch": [0, 1, 2, 6, 8, 9], "size": [0, 1, 2, 5, 6, 8], "divid": [0, 2], "The": [0, 1, 4, 5, 6, 8], "below": [0, 9], "similar": [0, 9], "from": [0, 1, 3, 4, 5, 6, 7, 8, 9], "user_featur": 0, "item_featur": 0, "respect": [0, 9], "11": [0, 1, 9], "12": [0, 1, 9], "21": 0, "22": 0, "23": 0, "creat": [0, 1, 5, 7], "kjt": [0, 1, 6, 8, 9], "print": [0, 5, 6, 8, 9], "help": [0, 3], "determin": [0, 7, 8], "best": [0, 7], "evalu": 0, "possibl": 0, "assess": 0, "memori": [0, 2, 4, 7, 8], "constraint": [0, 4, 8], "hardwar": 0, "estim": [0, 8], "comput": [0, 1, 2, 5, 6, 8, 9], "requir": [0, 2], "base": [0, 2, 6, 8], "fetch": [0, 8], "lookup": [0, 1, 2, 6, 8], "address": [0, 3, 7], "factor": [0, 8], "consid": [0, 1, 6, 8], "other": [0, 5, 8], "bandwidth": [0, 8], "To": [0, 9], "ensur": 0, "accur": 0, "consider": 0, "incorpor": 0, "inform": [0, 2, 8], "topolog": [0, 7, 8], "variou": 0, "outlin": 0, "some": [0, 1, 5, 7, 9], "well": [0, 2, 5], "benefit": [0, 2, 7], "limit": [0, 4], "find": [0, 3, 8], "your": [0, 3, 9], "do": [0, 1, 2, 5, 8], "split": [0, 1], "whether": [0, 1, 3, 5, 6, 8], "should": [0, 1, 5, 8, 9], "cut": 0, "up": [0, 2, 3], "keep": 0, "few": 0, "copi": [0, 1, 2, 5], "so": [0, 1, 2, 6, 7], "piec": 0, "outcom": 0, "part": [0, 7], "refer": [0, 2, 5, 9], "figur": [0, 2], "visual": [0, 1], "placement": [0, 8], "under": 0, "scheme": 0, "offer": [0, 3], "all": [0, 1, 5, 6, 7, 8], "avail": [0, 5], "tw": [0, 8], "suggest": [0, 3], "kept": 0, "whole": [0, 5], "place": [0, 1, 8], "rank": [0, 1, 8], "cw": [0, 8], "along": [0, 1], "emb_dim": 0, "dimens": [0, 1, 2, 6], "256": 0, "4": [0, 1, 6, 8, 9], "64": 0, "rw": [0, 8], "hash_siz": 0, "usual": [0, 2], "evenli": 0, "among": 0, "twrw": [0, 8], "host": [0, 8], "grid": 0, "gs": 0, "dp": [0, 8], "onc": 0, "convert": 0, "version": [0, 4, 6], "themselv": 0, "known": [0, 1], "shardedembeddingcollect": [0, 6], "shardedembeddingbagcollect": [0, 6], "handl": [0, 2], "gradient": [0, 2], "mani": [0, 7, 9], "There": [0, 2, 3], "cost": [0, 8], "associ": 0, "conjunct": 0, "gpu": [0, 2, 9], "where": [0, 1, 2, 6, 8], "vector": [0, 2], "pass": [0, 1, 2, 5, 6, 9], "updat": [0, 2, 5, 7, 8], "backward": [0, 2, 8], "ad": [0, 2, 3, 5], "need": [0, 1, 2, 3, 5, 6], "ask": 0, "all2al": 0, "given": [0, 1, 2, 8], "locat": 0, "send": 0, "target": 0, "That": [0, 1], "return": [0, 1, 2, 4, 5, 6, 8], "back": 0, "origin": [0, 4, 5], "sent": 0, "accordingli": 0, "describ": [0, 2], "abov": [0, 1, 2, 9], "three": 0, "stage": 0, "input_dist": 0, "form": [0, 6], "appropri": 0, "devic": [0, 1, 4, 5, 6, 7, 8, 9], "relev": [0, 8], "after": [0, 5, 6, 7, 8], "exchang": 0, "output_dist": [0, 8], "receiv": 0, "doe": [0, 1], "oper": [0, 1, 8], "revers": 0, "order": [0, 5, 8], "diagram": [0, 2], "culmin": 0, "entrypoint": 0, "integr": [0, 7, 9], "At": 0, "level": 0, "initi": [0, 5, 6], "set": [0, 3, 5, 8], "process": [0, 2, 5, 8], "assign": [0, 5], "default": [0, 1, 4, 5, 6, 8], "embeddingbagcollectionshard": [0, 5, 8], "none": [0, 1, 4, 5, 6, 8], "replac": 0, "them": [0, 1, 2, 5], "By": [0, 7], "wrap": [0, 5, 8], "distributeddataparallel": 0, "both": [0, 5, 9], "seamless": 0, "api": [0, 4, 5, 7, 8], "fuse": [0, 2], "step": [0, 3], "signific": [0, 2], "decreas": 0, "alongsid": 0, "granular": 0, "distinct": [0, 6], "paramet": [0, 1, 4, 5, 6, 8], "sensit": [0, 6], "two": [0, 2, 8], "quantiz": [0, 4], "lower": 0, "latenc": 0, "reduc": [0, 6], "let": [0, 9], "minim": 0, "c": [0, 1, 4, 5, 7], "even": 0, "further": 0, "ran": [0, 9], "being": [0, 4, 5, 7], "readi": 0, "automat": [0, 1, 7], "fbgemm": [0, 7, 9], "tbe": 0, "compil": [0, 4], "torchscript": [0, 4], "compat": [0, 8], "notebook": 0, "torchrec": [1, 4, 5, 6, 8], "otherwis": [1, 5, 8], "indic": [1, 6], "meant": [1, 6], "fed": 1, "For": [1, 2, 6, 9], "therefor": [1, 9], "amount": 1, "cover": 1, "class": [1, 5, 6, 8], "jaggedtensor": [1, 6, 9], "keyedjaggedtensor": [1, 6, 9], "jagged_tensor": [1, 9], "arg": [1, 5], "kwarg": [1, 5], "option": [1, 4, 5, 6, 8], "weight": [1, 4, 5, 6, 8], "whose": 1, "slice": 1, "mai": [1, 9], "see": [1, 5, 8, 9], "full": 1, "implement": [1, 4], "jit": 1, "script": 1, "abl": [1, 2, 9], "NOT": 1, "valid": [1, 8], "expens": 1, "alwai": [1, 3], "etc": 1, "dens": [1, 8], "have": [1, 2, 3, 6, 8, 9], "shape": [1, 6], "cumul": 1, "get": [1, 2], "static": 1, "empti": 1, "is_weight": [1, 6, 8], "bool": [1, 5, 6, 8], "fals": [1, 5, 6, 8], "values_dtyp": 1, "dtype": [1, 4], "weights_dtyp": 1, "lengths_dtyp": 1, "int32": 1, "construct": [1, 6], "from_dens": 1, "b": [1, 2, 6], "len": [1, 6], "2d": [1, 2], "7": [1, 6, 9], "8": [1, 6, 9], "10": [1, 6, 9], "j1": 1, "from_dense_length": 1, "note": [1, 2, 6], "still": [1, 5], "If": [1, 3, 4, 5, 6, 8, 9], "lengths_or_non": 1, "offsets_or_non": 1, "record_stream": 1, "stream": 1, "http": [1, 3, 9], "org": [1, 9], "doc": 1, "stabl": [1, 9], "html": [1, 3], "non_block": 1, "move": 1, "specifi": [1, 8], "asynchron": 1, "to_dens": 1, "6": [1, 6, 8], "inttensor": 1, "values_list": 1, "to_dense_weight": 1, "weights_list": 1, "to_padded_dens": 1, "desired_length": 1, "int": [1, 4, 6, 8], "padding_valu": 1, "float": [1, 6, 8], "n": [1, 2], "self": [1, 4, 5, 8], "longest": 1, "select": [1, 8], "last": 1, "dt": 1, "to_padded_dense_weight": 1, "instead": [1, 2, 5, 8], "d_wt": 1, "throw": 1, "error": [1, 8], "weights_or_non": 1, "first": [1, 5, 8, 9], "str": [1, 4, 5, 6, 8], "stride": 1, "per": [1, 2, 5, 8], "stride_per_key_per_rank": 1, "outer": 1, "inner": 1, "distribut": [1, 2, 3, 4, 5, 7, 8], "context": 1, "length_per_kei": 1, "offset_per_kei": [1, 6], "final": [1, 6, 8], "index_per_kei": 1, "dict": [1, 4, 5, 6, 8], "jt_dict": 1, "dictionari": [1, 5], "abil": [1, 9], "to_dict": 1, "lazi": [1, 5], "cacheabl": 1, "inverse_indic": 1, "tupl": [1, 4, 5], "invers": 1, "expand": [1, 6], "dedupl": 1, "dim_1": 1, "feature0": 1, "v0": 1, "v1": 1, "v2": 1, "feature1": 1, "v3": 1, "v4": 1, "v5": 1, "v6": 1, "v7": 1, "dim_0": 1, "ie": [1, 8], "second": 1, "dim_2": 1, "between": [1, 2, 8], "v": 1, "ani": [1, 3, 5, 8], "datatyp": [1, 6], "w0": 1, "w1": 1, "w2": 1, "w3": 1, "w4": 1, "w5": 1, "w6": 1, "w7": 1, "w": 1, "correspond": [1, 2, 5, 6, 9], "concat": 1, "kjt_list": 1, "concaten": 1, "singl": [1, 2, 6, 8], "empty_lik": 1, "from_jt_dict": [1, 9], "sync": 1, "newli": 1, "onli": [1, 5, 8, 9], "implicit": 1, "batch_siz": [1, 8], "basic": [1, 7, 9], "d": [1, 6], "format": 1, "x": [1, 6], "variable_feature_dim": 1, "could": 1, "just": [1, 8], "But": 1, "didn": 1, "t": [1, 2, 8], "now": [1, 9], "left": 1, "out": [1, 2, 9], "fail": 1, "correctli": [1, 9], "technic": 1, "know": 1, "correct": 1, "within": [1, 3, 5, 8], "essenti": 1, "infer": [1, 5, 6, 7, 8], "violat": 1, "exist": [1, 5, 6, 7, 8], "assumpt": 1, "precondit": 1, "fix": [1, 3], "from_lengths_sync": 1, "from_offsets_sync": [1, 6], "except": [1, 5], "inverse_indices_or_non": 1, "don": [1, 2], "length_per_key_or_non": 1, "hasn": 1, "been": [1, 2], "yet": 1, "lengths_offset_per_kei": 1, "offset_per_key_or_non": 1, "permut": 1, "indices_tensor": 1, "segment": [1, 2], "stride_per_kei": 1, "synchron": 1, "desir": [1, 4, 8], "non": [1, 6], "block": 1, "fashion": [1, 8], "Will": [1, 8], "cach": [1, 8], "result": [1, 2, 5, 6, 8, 9], "_jt_dict": 1, "unsync": 1, "clear": 1, "variable_stride_per_kei": 1, "hold": 1, "common": [1, 2, 7], "pool": [1, 2, 6, 8, 9], "key_dim": 1, "zero": 1, "kt": [1, 6], "tensor_list": 1, "from_tensor_list": 1, "cat_dim": 1, "alreadi": 1, "regroup": 1, "keyed_tensor": 1, "regroup_as_dict": 1, "shard": [2, 3, 4, 5, 6, 7, 8], "optim": [2, 4, 5, 6, 7, 8], "emploi": 2, "complex": [2, 3], "across": [2, 8], "enhanc": [2, 3], "manag": 2, "util": [2, 7], "effect": [2, 8], "primit": [2, 7], "hybrid": 2, "planner": 2, "pipelin": [2, 8], "train": [2, 3, 4, 5, 7, 8], "more": [2, 7, 8], "modern": 2, "deep": 2, "becom": 2, "successfulli": 2, "suffici": [2, 9], "time": [2, 5, 8], "paradigm": 2, "approach": 2, "develop": [2, 7, 9], "focus": 2, "latter": [2, 5], "comparison": 2, "workload": 2, "independ": 2, "suitabl": 2, "fit": 2, "entir": 2, "subset": 2, "contribut": 2, "overal": 2, "effec": 2, "dataset": 2, "usag": [2, 5, 8], "particularli": 2, "benefici": 2, "enabl": [2, 8], "dlrm": 2, "what": 2, "relationship": 2, "dimension": 2, "space": [2, 8], "mean": [2, 6, 7], "word": 2, "imag": 2, "aggreg": 2, "matrix": [2, 9], "most": [2, 4, 7, 8], "commonli": 2, "movi": 2, "titl": 2, "when": [2, 5, 8, 9], "choic": 2, "re": 2, "give": 2, "rise": 2, "question": 2, "techniqu": [2, 3, 7], "sum": [2, 6, 8, 9], "produc": [2, 6], "nn": [2, 4, 5, 6, 8], "embeddingbag": [2, 6, 8], "build": [2, 3, 7, 9], "modul": [2, 4, 5, 7, 8], "collect": [2, 6, 8], "extens": 2, "kernel": [2, 8], "improv": [2, 3, 7], "flow": 2, "show": [2, 9], "grai": 2, "sinc": [2, 5, 8], "fulli": 2, "materi": 2, "reduct": 2, "concept": 2, "go": [2, 3], "page": 2, "understand": [2, 9], "fundament": 2, "everyth": 2, "ti": 2, "togeth": [2, 9], "lot": 2, "ddp": [2, 5], "tutori": [2, 3], "special": [3, 7], "librari": [3, 7, 9], "ecosystem": [3, 7], "tailor": 3, "deploi": [3, 7], "nich": 3, "directli": [3, 5], "standard": [3, 6], "advanc": [3, 7], "massiv": [3, 7], "capabl": [3, 7], "topic": 3, "overview": 3, "short": 3, "intro": 3, "why": 3, "instal": 3, "our": 3, "life": 3, "colab": 3, "research": 3, "googl": 3, "com": 3, "github": 3, "blob": 3, "torchrec_introduct": 3, "ipynb": 3, "feedback": [3, 8], "interest": 3, "project": 3, "visit": 3, "repositori": 3, "sourc": [3, 9], "code": [3, 7, 9], "issu": 3, "ongo": 3, "submit": 3, "encount": 3, "bug": 3, "pleas": [3, 5], "tracker": 3, "propos": [3, 8], "chang": [3, 9], "fork": 3, "pull": 3, "request": 3, "sure": 3, "md": 3, "repo": 3, "easi": 4, "transform": [4, 7], "author": [4, 7], "via": [4, 9], "eager": 4, "swap": [4, 9], "fx": 4, "intend": 4, "quantize_inference_model": 4, "shard_quant_model": 4, "quantization_map": 4, "per_table_weight_dtyp": 4, "fp_weight_dtyp": 4, "int8": 4, "quantization_dtyp": 4, "output_dtyp": 4, "float32": 4, "counterpart": 4, "e": [4, 5, 8], "g": [4, 5], "quantembeddingbagcollect": 4, "map": [4, 8], "quantembeddingcollect": 4, "processor": 4, "featureprocessedembeddingbagcollect": 4, "ebc": [4, 6, 8, 9], "eb_config": [4, 8], "meta": [4, 5, 7, 8], "dlrmpredictmodul": 4, "embedding_bag_collect": 4, "dense_in_featur": 4, "model_config": 4, "dense_arch_layer_s": 4, "over_arch_layer_s": 4, "id_list_features_kei": 4, "dense_devic": 4, "quant_model": 4, "world_siz": [4, 8], "compute_devic": [4, 8], "cuda": [4, 9], "sharding_devic": 4, "moduleshard": [4, 5, 8], "device_memory_s": 4, "parameterconstraint": [4, 8], "ddr_cap": 4, "shardingplan": [4, 5, 8], "necessari": 4, "run": [4, 5, 6], "quantembeddingbagcollectionshard": 4, "quantembeddingcollectionshard": 4, "quantfeatureprocessedembeddingbagcollectionshard": 4, "tablewis": 4, "sharded_model": 4, "_": 4, "distributedmodelparallel": [5, 8], "model_parallel": 5, "env": 5, "shardingenv": 5, "init_data_parallel": 5, "true": [5, 8], "init_paramet": 5, "data_parallel_wrapp": 5, "dataparallelwrapp": 5, "cpu": [5, 9], "embeddingshardingplann": [5, 8], "collective_plan": [5, 8], "i": [5, 6, 8], "delai": 5, "until": 5, "custom": 5, "no_grad": 5, "def": 5, "init_weight": 5, "m": 5, "isinst": 5, "linear": 5, "fill_": 5, "elif": 5, "param": 5, "init": [5, 6], "kaiming_normal_": 5, "mymodel": 5, "appli": [5, 6], "recurs": 5, "submodul": 5, "shardedmodul": 5, "defin": [5, 6], "everi": 5, "overridden": 5, "subclass": 5, "although": 5, "recip": 5, "instanc": 5, "afterward": 5, "former": 5, "care": 5, "regist": 5, "hook": 5, "while": [5, 7], "silent": 5, "ignor": 5, "tor": 5, "argument": [5, 6], "safe": 5, "method": [5, 6, 7], "load_state_dict": 5, "state_dict": 5, "ordereddict": 5, "prefix": 5, "strict": 5, "_incompatiblekei": 5, "buffer": 5, "descend": [5, 8], "must": 5, "exactli": 5, "match": [5, 9], "unless": 5, "get_swap_module_params_on_convers": 5, "persist": 5, "strictli": 5, "enforc": 5, "properti": [5, 6], "current": [5, 8, 9], "preserv": 5, "wherea": 5, "state": [5, 7], "requires_grad": 5, "field": 5, "missing_kei": 5, "expect": [5, 8], "miss": 5, "unexpected_kei": 5, "present": 5, "namedtupl": 5, "rais": 5, "runtimeerror": 5, "fsdp": 5, "dmp": 5, "named_buff": 5, "remove_dupl": 5, "iter": [5, 8], "over": 5, "yield": 5, "itself": 5, "prepend": 5, "direct": 5, "member": 5, "remov": 5, "duplic": 5, "xdoctest": 5, "skip": 5, "undefin": 5, "var": 5, "buf": 5, "running_var": 5, "named_paramet": 5, "bia": 5, "destin": 5, "keep_var": 5, "averag": [5, 8], "object": 5, "shallow": 5, "also": [5, 9], "accept": 5, "posit": [5, 6], "howev": 5, "deprec": 5, "keyword": 5, "futur": 5, "releas": [5, 9], "avoid": 5, "compos": [5, 8], "detach": 5, "autograd": 5, "config": 6, "embeddingbagconfig": [6, 9], "embeddingconfig": 6, "embedding_config": 6, "num_embed": [6, 9], "embedding_dim": [6, 9], "data_typ": 6, "fp32": 6, "feature_nam": [6, 9], "factori": 6, "weight_init_max": 6, "weight_init_min": 6, "num_embeddings_post_prun": 6, "init_fn": 6, "callabl": [6, 8], "need_po": 6, "poolingtyp": [6, 9], "baseembeddingconfig": 6, "dataclass": 6, "max": [6, 8], "min": 6, "prune": 6, "embedding_modul": 6, "unshard": 6, "scenario": 6, "f": 6, "l": 6, "potenti": 6, "j": 6, "bag": 6, "cat": 6, "emb": 6, "mode": 6, "table_0": 6, "t1": 6, "f1": 6, "table_1": 6, "t2": 6, "f2": 6, "pooled_embed": 6, "dim": 6, "8899": 6, "1342": 6, "9060": 6, "0905": 6, "2814": 6, "9369": 6, "7783": 6, "0000": 6, "1598": 6, "0695": 6, "3265": 6, "1011": 6, "4256": 6, "1846": 6, "1648": 6, "0893": 6, "3590": 6, "9784": 6, "7681": 6, "grad_fn": 6, "catbackward0": 6, "embedding_bag_config": 6, "reset_paramet": 6, "reset": 6, "intiial": 6, "need_indic": 6, "eb": 6, "equal": 6, "rang": 6, "e1_config": 6, "e2_config": 6, "ec": 6, "feature_embed": 6, "2050": 6, "5478": 6, "6054": 6, "7352": 6, "3210": 6, "0399": 6, "1279": 6, "1756": 6, "4130": 6, "7519": 6, "4341": 6, "0499": 6, "9329": 6, "0697": 6, "8095": 6, "embeddingbackward": 6, "embedding_names_by_t": 6, "individu": 6, "art": 7, "person": 7, "path": [7, 8], "product": [7, 9], "wide": 7, "adopt": 7, "workflow": 7, "uniqu": 7, "challeng": 7, "focu": 7, "regular": 7, "simplist": 7, "flexibl": 7, "customiz": 7, "balanc": [7, 8], "support": 7, "sophist": 7, "incred": 7, "top": 7, "power": 7, "largest": [7, 8], "frictionless": 7, "deploy": 7, "load": [7, 8], "built": 7, "seamlessli": 7, "tool": 7, "leverag": 7, "knowledg": 7, "codebas": 7, "robust": 7, "continu": 7, "come": 7, "respons": 8, "moduleshardingplan": 8, "fqn": 8, "larger": 8, "embeddingmoduleshardingplan": 8, "spec": 8, "get_plan_for_modul": 8, "module_path": 8, "enumer": 8, "storage_reserv": 8, "storagereserv": 8, "union": 8, "partition": 8, "performance_model": 8, "perfmodel": 8, "stat": 8, "debug": 8, "callback": 8, "shardingopt": 8, "shardabl": 8, "reserv": 8, "pg": 8, "processgroup": 8, "broadcast": 8, "dist": 8, "embeddingenumer": 8, "shardestim": 8, "use_exact_enumerate_ord": 8, "exact": 8, "name_children": 8, "popul": 8, "populate_estim": 8, "sharding_opt": 8, "descript": 8, "greedyperfpartition": 8, "sort_bi": 8, "sortbi": 8, "balance_modul": 8, "greedi": 8, "sort": 8, "perf": 8, "smaller": 8, "wai": 8, "partit": 8, "storage_constraint": 8, "partition_bi": 8, "attribut": 8, "uniform": 8, "total": 8, "docstr": 8, "partition_by_devic": 8, "done": 8, "clariti": 8, "heuristicalstoragereserv": 8, "percentag": 8, "parameter_multipli": 8, "dense_tensor_estim": 8, "heurist": 8, "calcul": 8, "extra": 8, "percent": 8, "act": 8, "margin": 8, "beyond": 8, "multipli": 8, "greedypropos": 8, "use_depth": 8, "threshold": 8, "On": 8, "tri": 8, "next": 8, "earli": 8, "stop": 8, "consecut": 8, "wors": 8, "perf_rat": 8, "than": 8, "best_perf_r": 8, "rate": 8, "search_spac": 8, "search": 8, "shard_estim": 8, "embeddingperfestim": 8, "is_infer": 8, "wall": 8, "sharder_map": 8, "classmethod": 8, "perf_func_emb_wall_tim": 8, "shard_siz": 8, "compute_kernel": 8, "sharding_typ": 8, "local_world_s": 8, "input_length": 8, "input_data_type_s": 8, "table_data_type_s": 8, "output_data_type_s": 8, "fwd_a2a_comm_data_type_s": 8, "bwd_a2a_comm_data_type_s": 8, "fwd_sr_comm_data_type_s": 8, "bwd_sr_comm_data_type_s": 8, "num_pool": 8, "hbm_mem_bw": 8, "ddr_mem_bw": 8, "hbm_to_ddr_mem_bw": 8, "intra_host_bw": 8, "inter_host_bw": 8, "bwd_compute_multipli": 8, "weighted_feature_bwd_compute_multipli": 8, "is_pool": 8, "caching_ratio": 8, "prefetch_pipelin": 8, "expected_cache_fetch": 8, "uneven_sharding_perf_multipli": 8, "attempt": 8, "rel": 8, "local_row": 8, "local_col": 8, "queri": 8, "data_parallel": 8, "fwd_comm_data_type_s": 8, "dure": 8, "bwd_comm_data_type_s": 8, "sampl": 8, "hbm": 8, "ddr": 8, "hbm_to_ddr_bw": 8, "thread": 8, "machin": 8, "unpool": 8, "sequenti": 8, "signifi": 8, "score": 8, "ratio": 8, "prefetch": 8, "global": 8, "account": 8, "uneven": 8, "embeddingstorageestim": 8, "pipeline_typ": 8, "pipelinetyp": 8, "run_embedding_at_peak_memori": 8, "replic": 8, "fwd": 8, "bwd": 8, "execut": [8, 9], "peak": 8, "temporari": 8, "alloc": 8, "long": 8, "befor": 8, "count": 8, "toward": 8, "won": 8, "ll": [8, 9], "hidden": 8, "affect": 8, "old": 8, "agnost": 8, "formula": 8, "recsi": 8, "happen": [8, 9], "forwrad": 8, "begin": 8, "routin": 9, "test": 9, "aw": 9, "linux": 9, "python": 9, "9": 9, "platform": 9, "asid": 9, "those": 9, "core": 9, "depend": 9, "upon": 9, "furthermor": 9, "cu121": 9, "cu118": 9, "cu124": 9, "pip": 9, "url": 9, "download": 9, "whl": 9, "torchmetr": 9, "pypi": 9, "nightli": 9, "latest": 9, "check": 9, "properli": 9, "import": 9, "product_t": 9, "16": 9, "4096": 9, "user_t": 9, "product_jt": 9, "user_jt": 9, "q1": 9, "save": 9, "file": 9, "torchrec_exampl": 9, "py": 9, "Then": 9, "termin": 9, "congrat": 9, "program": 9}, "objects": {"torchrec.distributed": [[5, 0, 0, "-", "model_parallel"], [8, 0, 0, "-", "types"]], "torchrec.distributed.model_parallel": [[5, 1, 1, "", "DistributedModelParallel"]], "torchrec.distributed.model_parallel.DistributedModelParallel": [[5, 2, 1, "", "copy"], [5, 2, 1, "", "forward"], [5, 2, 1, "", "init_data_parallel"], [5, 2, 1, "", "load_state_dict"], [5, 3, 1, "", "module"], [5, 2, 1, "", "named_buffers"], [5, 2, 1, "", "named_parameters"], [5, 2, 1, "", "state_dict"]], "torchrec.distributed.planner": [[8, 0, 0, "-", "enumerators"], [8, 0, 0, "-", "partitioners"], [8, 0, 0, "-", "planners"], [8, 0, 0, "-", "proposers"], [8, 0, 0, "module-0", "shard_estimators"], [8, 0, 0, "-", "storage_reservations"]], "torchrec.distributed.planner.enumerators": [[8, 1, 1, "", "EmbeddingEnumerator"]], "torchrec.distributed.planner.enumerators.EmbeddingEnumerator": [[8, 2, 1, "", "enumerate"], [8, 2, 1, "", "populate_estimates"]], "torchrec.distributed.planner.partitioners": [[8, 1, 1, "", "GreedyPerfPartitioner"]], "torchrec.distributed.planner.partitioners.GreedyPerfPartitioner": [[8, 2, 1, "", "partition"]], "torchrec.distributed.planner.planners": [[8, 1, 1, "", "EmbeddingShardingPlanner"]], "torchrec.distributed.planner.planners.EmbeddingShardingPlanner": [[8, 2, 1, "", "collective_plan"], [8, 2, 1, "", "plan"]], "torchrec.distributed.planner.proposers": [[8, 1, 1, "", "GreedyProposer"]], "torchrec.distributed.planner.proposers.GreedyProposer": [[8, 2, 1, "", "feedback"], [8, 2, 1, "", "load"], [8, 2, 1, "", "propose"]], "torchrec.distributed.planner.shard_estimators": [[8, 1, 1, "", "EmbeddingPerfEstimator"], [8, 1, 1, "", "EmbeddingStorageEstimator"]], "torchrec.distributed.planner.shard_estimators.EmbeddingPerfEstimator": [[8, 2, 1, "", "estimate"], [8, 2, 1, "", "perf_func_emb_wall_time"]], "torchrec.distributed.planner.shard_estimators.EmbeddingStorageEstimator": [[8, 2, 1, "", "estimate"]], "torchrec.distributed.planner.storage_reservations": [[8, 1, 1, "", "HeuristicalStorageReservation"]], "torchrec.distributed.types": [[8, 1, 1, "", "ShardingPlan"]], "torchrec.distributed.types.ShardingPlan": [[8, 2, 1, "", "get_plan_for_module"], [8, 4, 1, "", "plan"]], "torchrec.inference": [[4, 0, 0, "-", "modules"]], "torchrec.inference.modules": [[4, 5, 1, "", "quantize_inference_model"], [4, 5, 1, "", "shard_quant_model"]], "torchrec.modules": [[6, 0, 0, "-", "embedding_configs"], [6, 0, 0, "-", "embedding_modules"]], "torchrec.modules.embedding_configs": [[6, 1, 1, "", "BaseEmbeddingConfig"], [6, 1, 1, "", "EmbeddingBagConfig"], [6, 1, 1, "", "EmbeddingConfig"]], "torchrec.modules.embedding_modules": [[6, 1, 1, "", "EmbeddingBagCollection"], [6, 1, 1, "", "EmbeddingCollection"]], "torchrec.modules.embedding_modules.EmbeddingBagCollection": [[6, 3, 1, "", "device"], [6, 2, 1, "", "embedding_bag_configs"], [6, 2, 1, "", "forward"], [6, 2, 1, "", "is_weighted"], [6, 2, 1, "", "reset_parameters"]], "torchrec.modules.embedding_modules.EmbeddingCollection": [[6, 3, 1, "", "device"], [6, 2, 1, "", "embedding_configs"], [6, 2, 1, "", "embedding_dim"], [6, 2, 1, "", "embedding_names_by_table"], [6, 2, 1, "", "forward"], [6, 2, 1, "", "need_indices"], [6, 2, 1, "", "reset_parameters"]], "torchrec.sparse": [[1, 0, 0, "-", "jagged_tensor"]], "torchrec.sparse.jagged_tensor": [[1, 1, 1, "", "JaggedTensor"], [1, 1, 1, "", "KeyedJaggedTensor"], [1, 1, 1, "", "KeyedTensor"]], "torchrec.sparse.jagged_tensor.JaggedTensor": [[1, 2, 1, "", "device"], [1, 2, 1, "", "empty"], [1, 2, 1, "", "from_dense"], [1, 2, 1, "", "from_dense_lengths"], [1, 2, 1, "", "lengths"], [1, 2, 1, "", "lengths_or_none"], [1, 2, 1, "", "offsets"], [1, 2, 1, "", "offsets_or_none"], [1, 2, 1, "", "record_stream"], [1, 2, 1, "", "to"], [1, 2, 1, "", "to_dense"], [1, 2, 1, "", "to_dense_weights"], [1, 2, 1, "", "to_padded_dense"], [1, 2, 1, "", "to_padded_dense_weights"], [1, 2, 1, "", "values"], [1, 2, 1, "", "weights"], [1, 2, 1, "", "weights_or_none"]], "torchrec.sparse.jagged_tensor.KeyedJaggedTensor": [[1, 2, 1, "", "concat"], [1, 2, 1, "", "device"], [1, 2, 1, "", "empty"], [1, 2, 1, "", "empty_like"], [1, 2, 1, "", "from_jt_dict"], [1, 2, 1, "", "from_lengths_sync"], [1, 2, 1, "", "from_offsets_sync"], [1, 2, 1, "", "index_per_key"], [1, 2, 1, "", "inverse_indices"], [1, 2, 1, "", "inverse_indices_or_none"], [1, 2, 1, "", "keys"], [1, 2, 1, "", "length_per_key"], [1, 2, 1, "", "length_per_key_or_none"], [1, 2, 1, "", "lengths"], [1, 2, 1, "", "lengths_offset_per_key"], [1, 2, 1, "", "lengths_or_none"], [1, 2, 1, "", "offset_per_key"], [1, 2, 1, "", "offset_per_key_or_none"], [1, 2, 1, "", "offsets"], [1, 2, 1, "", "offsets_or_none"], [1, 2, 1, "", "permute"], [1, 2, 1, "", "record_stream"], [1, 2, 1, "", "split"], [1, 2, 1, "", "stride"], [1, 2, 1, "", "stride_per_key"], [1, 2, 1, "", "stride_per_key_per_rank"], [1, 2, 1, "", "sync"], [1, 2, 1, "", "to"], [1, 2, 1, "", "to_dict"], [1, 2, 1, "", "unsync"], [1, 2, 1, "", "values"], [1, 2, 1, "", "variable_stride_per_key"], [1, 2, 1, "", "weights"], [1, 2, 1, "", "weights_or_none"]], "torchrec.sparse.jagged_tensor.KeyedTensor": [[1, 2, 1, "", "device"], [1, 2, 1, "", "from_tensor_list"], [1, 2, 1, "", "key_dim"], [1, 2, 1, "", "keys"], [1, 2, 1, "", "length_per_key"], [1, 2, 1, "", "offset_per_key"], [1, 2, 1, "", "record_stream"], [1, 2, 1, "", "regroup"], [1, 2, 1, "", "regroup_as_dict"], [1, 2, 1, "", "to"], [1, 2, 1, "", "to_dict"], [1, 2, 1, "", "values"]]}, "objtypes": {"0": "py:module", "1": "py:class", "2": "py:method", "3": "py:property", "4": "py:attribute", "5": "py:function"}, "objnames": {"0": ["py", "module", "Python module"], "1": ["py", "class", "Python class"], "2": ["py", "method", "Python method"], "3": ["py", "property", "Python property"], "4": ["py", "attribute", "Python attribute"], "5": ["py", "function", "Python function"]}, "titleterms": {"torchrec": [0, 2, 3, 7, 9], "concept": 0, "jaggedtensor": 0, "keyedjaggedtensor": 0, "planner": [0, 8], "shard": 0, "embeddingt": 0, "distribut": 0, "train": 0, "modul": [0, 6], "distributedmodelparallel": 0, "optim": 0, "infer": [0, 4], "see": [0, 2], "also": [0, 2], "data": 1, "type": 1, "high": 2, "level": 2, "architectur": 2, "s": 2, "parallel": [2, 5], "strategi": 2, "model": [2, 5], "embed": 2, "tabl": 2, "welcom": 3, "document": 3, "get": 3, "start": 3, "how": 3, "contribut": 3, "overview": 7, "why": 7, "set": 9, "up": 9, "system": 9, "requir": 9, "version": 9, "compat": 9, "instal": 9, "run": 9, "simpl": 9, "exampl": 9}, "envversion": {"sphinx.domains.c": 2, "sphinx.domains.changeset": 1, "sphinx.domains.citation": 1, "sphinx.domains.cpp": 6, "sphinx.domains.index": 1, "sphinx.domains.javascript": 2, "sphinx.domains.math": 2, "sphinx.domains.python": 3, "sphinx.domains.rst": 2, "sphinx.domains.std": 2, "sphinx.ext.intersphinx": 1, "sphinx": 56}})