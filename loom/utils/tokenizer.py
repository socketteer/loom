from transformers import GPT2Tokenizer

tok = None


def tokenize(input):
    tokenizer = tok if tok else GPT2Tokenizer.from_pretrained("gpt2")
    return tokenizer(input)["input_ids"]


def detokenize(tokens):
    tokenizer = tok if tok else GPT2Tokenizer.from_pretrained("gpt2")
    return tokenizer.convert_tokens_to_string(tokens)


def token_to_word(token):
    tokenizer = tok if tok else GPT2Tokenizer.from_pretrained("gpt2")
    return tokenizer.convert_ids_to_tokens([token])[0]


def logit_mask(mask):
    id_mask = {}
    for token in mask:
        if token == "\n":
            token_id = 198
        else:
            token_id = tokenize([token])[0][0]
        id_mask[token_id] = mask[token]
    return id_mask
