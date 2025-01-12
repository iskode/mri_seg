# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_dataprep.ipynb (unless otherwise specified).

__all__ = ['resize_slices', 'apply_trans', 'MRImage', 'MRImageSegment', 'loadnii', 'open_mri', 'open_mri_mask',
           'MRImageList', 'MRImageSegLabelList', 'MRISegItemList']

# Cell
from fastai import *
from fastai.vision import *
from fastai.data_block import *
import nibabel as nib
from fastai.callbacks import *
from fastai.vision.data import SegmentationProcessor

# Cell
def _resolve_tfms(tfms:TfmList):
    "Resolve every tfm in `tfms`."
    for f in listify(tfms): f.resolve()

def resize_slices(n, slices):
    slices = listify(slices)
    diff = len(slices) - n
    sl = []
    if diff>0:
        start = 0 #np.random.randint(0, diff)
        sl = [slices[i] for i in range(start, start+n)]
    else:
        sl = slices + [slices[i] for i in range(-diff)]
    assert n == len(sl), f'n={n}, len(new_slice)={len(sl)}'
    return sl


def apply_trans(tfms, slices, slicewise, cls=(None, None), **kwargs):
    "Apply different transformations on each slice if `slicewise` is True and the same ones otherwise"
    if 'size' in kwargs:
        size = kwargs['size']
        assert len(size) >= 2
        slices = resize_slices(size[0], slices)
        kwargs['size'] = size[1:]
    if slicewise: # this case creates mismatch between slices and their labels!
        print(f'"slicewise = True" creates mismatch between slices and their labels!')
        x = cls[0]([cls[1](s).apply_tfms(tfms, **kwargs).data for s in slices])
    else:
        if len(tfms[0].resolved) == 0: _resolve_tfms(tfms)
        kwargs['do_resolve'] = False
        x = cls[0]([cls[1](s).apply_tfms(tfms, **kwargs).data for s in slices])
    return x

class MRImage(ItemBase):

    def __init__(self, imageList:Collection[Tensor]):
        self.slices = imageList if is_listy(imageList) else listify(imageList)
        self.px = torch.stack(self.slices)

    @property
    def data(self)->TensorImage: return self.px

    @property
    def shape(self)->Tuple[int,int,int,int]: return tuple([*self.data.shape])
    @property
    def size(self)->Tuple[int,int]: return tuple(self.shape[-2:])
    @property
    def device(self)->torch.device: return self.data.device

    def __repr__(self): return f'{self.__class__.__name__} {tuple(self.shape)}'


    def apply_tfms(self, tfms, slicewise=False, **kwargs):
        return apply_trans(tfms, self.slices, slicewise, (MRImage, Image), **kwargs)

    def to_one(self):
        "Concatenate all slices into a single Image object"
        return Image(torch.cat([d for d in self.data], 2))

    def show(self, axs:plt.Axes=None, figsize:tuple=(40,40), title:Optional[str]=None, hide_axis:bool=True,
              cmap:str=None, y:Any=None, slice_idxs=np.arange(5), **kwargs):
        "Show image on `ax` with `title`, using `cmap` if single-channel, overlaid with optional `y`"
        cmap = ifnone(cmap, defaults.cmap)
        assert min(slice_idxs) >=0 and max(slice_idxs) <= self.shape[0]
        slices = [self.slices[i] for i in slice_idxs]
        cols = len(slices)
        fig,axs = plt.subplots(1, cols, figsize=figsize)
        if cols == 1: axs = [axs]
        assert len(axs) == len(slices)
        if y:
            yy = [y.slices[i] for i in slice_idxs]
            for x,y_,ax in zip(slices, yy, axs):
                Image(x).show(ax=ax, y=ImageSegment(y_), **kwargs)
        else:
            for x,ax in zip(slices, axs):
                Image(x).show(ax=ax, **kwargs)

# Cell
class MRImageSegment(MRImage):
    "Support applying transforms to segmentation masks data in `px`."
    @property
    def data(self)->TensorImage:
        "Return this MRImage pixels as a `LongTensor`."
        return self.px.long()

    def apply_tfms(self, tfms, slicewise=False, **kwargs):
        return apply_trans(tfms, self.slices, slicewise, (MRImageSegment, ImageSegment), **kwargs)

    def show(self, axs:plt.Axes=None, figsize:tuple=(40,40), title:Optional[str]=None, hide_axis:bool=True,
        cmap:str='tab20', alpha:float=0.5, slice_idxs=np.arange(5), **kwargs):
        "Show the `MRImageSegment` on `ax`."
        cmap = ifnone(cmap, defaults.cmap)
        assert min(slice_idxs) >=0 and max(slice_idxs) <= self.shape[0]
        slices = [self.slices[i] for i in slice_idxs]
        cols = len(slices)
        fig,axs = plt.subplots(1, cols, figsize=figsize)
        if cols == 1: axs = [axs]
        assert len(axs) == len(slices)
        for x,ax in zip(slices, axs):
            ImageSegment(x).show(ax=ax, **kwargs)

    def save(self, fn:PathOrStr):
        pass

    def reconstruct(self, t:Tensor): return MRImageSegment(t)


# Cell
def loadnii(fn):
    return nib.load(fn).get_data()

def open_mri(fn:PathOrStr, div:bool=True, convert_mode:str='RGB', loader=loadnii,  cls:type=MRImage,
             after_open:Callable=None)->MRImage:
    "Return ` MRImage` object created from any MRI file format `fn` using its custom `loader`."
    x = loader(fn)
    h, w , n_slices = x.shape
    res = []
    for i in range(n_slices):
        a = PIL.Image.fromarray(x[:,:,i]).convert(convert_mode)
        if after_open: a = after_open(a)
        a =  pil2tensor(a, np.float32)
        if div: a.div_(255)
        res.append(a)
    return cls(res)

def open_mri_mask(fn):
    return open_mri(fn, div=False, convert_mode='L', cls=MRImageSegment)

# Cell
class MRImageList(ImageList):
    def open(self, fn):
        "Open image in `fn`, subclass and overwrite for custom behavior."
        return open_mri(fn, convert_mode=self.convert_mode, after_open=self.after_open)

    def reconstruct(self, t:Tensor): return MRImage(t.float().clamp(min=0,max=1))

    def show_xys(self, xs, ys, imgsize:int=10, figsize:Optional[Tuple[int,int]]=None,
                 slice_idxs=np.arange(5), **kwargs):
        "Show the `xs` (inputs) and `ys` (targets) on a figure of `figsize`."
        for x,y in zip(xs, ys): x.show(y=y, slice_idxs=slice_idxs, **kwargs)

    def show_xyzs(self, xs, ys, zs, imgsize:int=10, figsize:Optional[Tuple[int,int]]=None,
                  slice_idxs=np.arange(5), **kwargs):
        "Show `xs` (inputs), `ys` (targets) and `zs` (predictions) on a figure of `figsize`."
        if self._square_show_res:
            raise Exception('Case not handle yet !')
        else:
            title = 'Ground truth/Predictions'
            for x,y,z in zip(xs,ys,zs):
                x.show(y=y, slice_idxs=slice_idxs, **kwargs)
                x.show(y=z, slice_idxs=slice_idxs, **kwargs)

class MRImageSegLabelList(MRImageList):
    "`ItemList` for segmentation masks."
    _processor=SegmentationProcessor
    def __init__(self, items:Iterator, classes:Collection=None, **kwargs):
        super().__init__(items, **kwargs)
        self.copy_new.append('classes')
        self.classes,self.loss_func = classes,CrossEntropyFlat(axis=2)
    # Custom label: mask opener
    def open(self, fn): return open_mri(fn, div=False, convert_mode='L', cls=MRImageSegment)

    def analyze_pred(self, pred): return pred.argmax(dim=1, keepdim=True)

    def reconstruct(self, t:Tensor): return MRImageSegment(t)

class MRISegItemList(MRImageList):
    "`ItemList` suitable for segmentation tasks."
    _label_cls,_square_show_res = MRImageSegLabelList,False
