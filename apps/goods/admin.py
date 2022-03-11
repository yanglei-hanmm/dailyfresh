from django.contrib import admin
from apps.goods.models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,GoodsSKU

# Register your models here.
admin.site.register(GoodsType)
admin.site.register(IndexGoodsBanner)
admin.site.register(IndexPromotionBanner)
admin.site.register(GoodsSKU)